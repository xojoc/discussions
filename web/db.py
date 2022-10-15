import datetime
import logging
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from web import (
    celery_util,
    crawler,
    email_util,
    mastodon,
    models,
    topics,
    twitter,
    worker,
    rank,
)

logger = logging.getLogger(__name__)


def __timing_iterate_all(chunk_size=10_000):
    start_time = time.monotonic()
    stories = models.Discussion.objects.all().order_by()
    for _ in stories.iterator(chunk_size=chunk_size):
        pass

    logger.info(f"db iterate all: {time.monotonic() - start_time}")


@shared_task(ignore_result=True, bind=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_update_discussions(self):
    start_time = time.monotonic()
    count_dirty = 0
    count_dirty_resource = 0
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)
    stories = models.Discussion.objects.filter(
        entry_updated_at__lte=seven_days_ago
    ).order_by()

    logger.info(f"db update discussions: count {stories.count()}")

    dirty_stories = []

    def __update(dirty_stories):
        updated_count = models.Discussion.objects.bulk_update(
            dirty_stories,
            ["canonical_story_url", "normalized_tags", "normalized_title"],
        )
        logger.info(f"db update: updated: {updated_count}")
        dirty_stories[:] = []

    last_checkpoint = time.monotonic()

    for story in stories.iterator(chunk_size=10_000):
        dirty = False

        if story.story_url:
            resource = models.Resource.by_url(story.story_url)
            if resource is None:
                crawler.add_to_queue(story.story_url, priority=3)

        canonical_story_url = story.canonical_story_url
        normalized_title = story.normalized_title
        normalized_tags = story.normalized_tags
        category = story.category

        story._pre_save()

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

        if len(dirty_stories) >= 1000:
            __update(dirty_stories)

        if time.monotonic() > last_checkpoint + 60:
            if worker.graceful_exit(self):
                logger.info("update discussions: graceful exit")
                break

            last_checkpoint = time.monotonic()

    if len(dirty_stories) > 0:
        __update(dirty_stories)

    logger.info(f"db update: total dirty: {count_dirty}")
    logger.info(f"db update: total resource dirty: {count_dirty_resource}")
    logger.info(f"db update: {time.monotonic() - start_time}")


@shared_task(ignore_result=True, bind=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_update_resources(self):
    start_time = time.monotonic()
    last_checkpoint = time.monotonic()

    seven_days_ago = timezone.now() - datetime.timedelta(days=7)
    resources = models.Resource.objects.filter(
        last_processed__lte=seven_days_ago
    ).order_by()

    logger.info(f"db update resources: count {resources.count()}")

    for resource in resources[:10_000].iterator(chunk_size=1000):
        crawler.extract_html(resource)

        if time.monotonic() > last_checkpoint + 60:
            if worker.graceful_exit(self):
                logger.info("update resources: graceful exit")
                break

            last_checkpoint = time.monotonic()

    logger.info(f"db update resources: {time.monotonic() - start_time}")


@shared_task(ignore_result=True, bind=True)
def update_pagerank(self):
    g = rank.links_to_graph()
    pagerank = rank.pagerank(g)

    r = models.Resource

    updated_count = models.Resource.objects.bulk_update(
        (r(pk=pk, pagerank=pr) for pk, pr in pagerank.items()),
        ["pagerank"],
    )

    logger.info(f"update_pagerank: {updated_count}")


@shared_task(ignore_result=True, bind=True)
def admin_send_recap_email(self):
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

    twitter_followers_count = twitter.get_followers_count(twitter_usernames)
    mastodon_followers_count = mastodon.get_followers_count(mastodon_usernames)

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

    for topic_key, topic in sorted_topics.items():
        twitter_count = 0
        mastodon_count = 0
        if topic.get("twitter"):
            twitter_count = twitter_followers_count.get(
                topic["twitter"]["account"]
            )
        if topic.get("mastodon"):
            user = topic["mastodon"]["account"].split("@")[1]
            mastodon_count = mastodon_followers_count.get(user)

        topic_subscribers = models.Subscriber.mailing_list(topic_key).count()

        body += f"{topic_key:20} => {topic_subscribers:9,} {mastodon_count:9,} {twitter_count:9,}\n"

    body += "\n"

    email_util.send(
        "[discu.eu] Weekly overview",
        body,
        settings.SERVER_EMAIL,
        settings.ADMINS[0][1],
    )
