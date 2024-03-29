# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import logging
import random
import time

from celery import shared_task
from django.utils import timezone

from web import (
    celery_util,
    crawler,
    email_util,
    mastodon_api,
    models,
    rank,
    topics,
    twitter_api,
    worker,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def worker_update_discussions(self):
    time.sleep(random.randint(10, 30))  # noqa: S311
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    start_time = time.monotonic()
    count_dirty = 0
    count_dirty_resource = 0
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)
    stories = models.Discussion.objects.filter(
        entry_updated_at__lte=seven_days_ago,
    ).order_by()

    logger.info(f"db update discussions START: count {stories.count()}")

    dirty_stories = []

    def __update(dirty_stories):
        updated_count = models.Discussion.objects.bulk_update(
            dirty_stories,
            ["canonical_story_url", "normalized_tags", "normalized_title"],
        )
        logger.info(f"db update discussions: updated: {updated_count}")
        dirty_stories[:] = []

    last_checkpoint = time.monotonic()

    for story in stories.iterator(chunk_size=10_000):
        dirty = False

        if story.story_url:
            resource = models.Resource.by_url(story.story_url)
            if resource is None:
                crawler.add_to_queue(
                    story.story_url,
                    crawler.Priority.very_low,
                )

        canonical_story_url = story.canonical_story_url
        normalized_title = story.normalized_title
        normalized_tags = story.normalized_tags
        category = story.category

        story.pre_save()

        if (
            story.canonical_story_url != canonical_story_url
            or story.normalized_title != normalized_title
            or story.normalized_tags != normalized_tags
            or story.category != category
        ):
            dirty = True

        if dirty:
            count_dirty += 1
            dirty_stories.append(story)

        batch_size = 1000

        if len(dirty_stories) >= batch_size:
            __update(dirty_stories)

        if time.monotonic() > last_checkpoint + 60:
            if worker.graceful_exit(self):
                logger.info("update discussions: graceful exit")
                break

            last_checkpoint = time.monotonic()

    if len(dirty_stories) > 0:
        __update(dirty_stories)

    logger.info(f"db update discussions: total dirty: {count_dirty}")
    logger.info(
        f"db update discussions: total resource dirty: {count_dirty_resource}",
    )
    logger.info(f"db update discussions END: {time.monotonic() - start_time}")


@shared_task(bind=True, ignore_result=True)
def worker_update_resources(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    start_time = time.monotonic()
    last_checkpoint = time.monotonic()

    seven_days_ago = timezone.now() - datetime.timedelta(days=7)
    resources = models.Resource.objects.filter(
        last_processed__lte=seven_days_ago,
    ).order_by()

    logger.info(f"db update resources START: count {resources.count()}")

    for resource in resources[:10_000].iterator(chunk_size=1000):
        crawler.extract_html(resource)

        if time.monotonic() > last_checkpoint + 60:
            if worker.graceful_exit(self):
                logger.info("update resources: graceful exit")
                break

            last_checkpoint = time.monotonic()

    logger.info(f"db update resources END: {time.monotonic() - start_time}")


@shared_task(ignore_result=True)
def update_pagerank():
    g = rank.links_to_graph()
    pagerank = rank.pagerank(g)

    total_updated_count = 0
    resources = []

    def __update(resources):
        if not resources:
            return
        updated_count = models.Resource.objects.bulk_update(
            resources,
            ["pagerank"],
        )
        nonlocal total_updated_count
        total_updated_count += updated_count
        resources[:] = []

    for pk, pr in pagerank.items():
        resources.append(models.Resource(pk=pk, pagerank=pr))

        batch_size = 2000
        if len(resources) >= batch_size:
            __update(resources)

    __update(resources)

    logger.info(f"update_pagerank: updated: {total_updated_count}")


@shared_task(ignore_result=True)
def admin_send_recap_email():
    subscribers = (
        models.Subscriber.mailing_list(None).distinct("email").count()
    )
    unconfirmed = (
        models.Subscriber.objects.filter(confirmed=False)
        .filter(unsubscribed=False)
        .count()
    )
    unsubscribed = models.Subscriber.objects.filter(unsubscribed=True).count()

    sorted_topics = dict(sorted(topics.topics.items()))
    twitter_usernames = []
    mastodon_usernames = []

    for topic in sorted_topics.values():
        if topic.get("twitter"):
            twitter_usernames.append(topic["twitter"]["account"])
        if topic.get("mastodon"):
            user = topic["mastodon"]["account"].split("@")[1]
            mastodon_usernames.append(user)

    twitter_followers_count = (
        twitter_api.get_followers_count(twitter_usernames) or {}
    )
    mastodon_followers_count = (
        mastodon_api.get_followers_count(mastodon_usernames) or {}
    )
    users_count = models.CustomUser.objects.count()

    users_premium_count = (
        models.CustomUser.objects.filter(premium_active=True)
        .filter(premium_cancelled=False)
        .count()
    )

    mention_rules_count = models.Mention.objects.all().count()
    mention_notifications_count = (
        models.MentionNotification.objects.all().count()
    )

    body = f"""
Users: {users_count}
Premium users: {users_premium_count}
Subscribers: {subscribers}
Unconfirmed: {unconfirmed}
Unsubscribed: {unsubscribed}

Mention rules: {mention_rules_count}
  notifications: {mention_notifications_count}

"""

    body += f"{'topic':20} => {'subs':<10} {'mastodon':<10} {'twitter':<10}\n"

    for topic_key, topic in sorted_topics.items():
        twitter_count = 0
        mastodon_count = 0
        if topic.get("twitter"):
            twitter_count = twitter_followers_count.get(
                topic["twitter"]["account"],
                0,
            )
        if topic.get("mastodon"):
            user = topic["mastodon"]["account"].split("@")[1]
            mastodon_count = mastodon_followers_count.get(user, 0)

        topic_subscribers = models.Subscriber.mailing_list(topic_key).count()

        body += f"{topic_key:20} => {topic_subscribers:<10} {mastodon_count:<10} {twitter_count:<10}\n"

    body += "\n"

    email_util.send_admins("[discu.eu] Weekly overview", body)
