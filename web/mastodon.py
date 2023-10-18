# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import logging
import os
import random
import time
import unicodedata

import sentry_sdk
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

from . import celery_util, extract, http, models, topics, util

logger = logging.getLogger(__name__)


def __sleep(a, b):
    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        return
    time.sleep(random.randint(a, b))


def __print(s):
    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        print(s)


def profile_url(account):
    parts = account.split("@")
    return f"https://{parts[2]}/@{parts[1]}"


def post(status, username, post_from_dev=False):
    account = topics.get_account_configuration("mastodon", username)
    access_token = account.get("token")

    if not access_token:
        logger.warning(f"Mastodon bot: {username} non properly configured")
        return None

    if not post_from_dev:
        if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
            random.seed()
            print(username)
            print(status)
            return random.randint(1, 1_000_000)

    client = http.client(with_cache=False)

    api_url = "https://mastodon.social/api/v1/statuses"
    auth = {"Authorization": f"Bearer {access_token}"}
    parameters = {"status": status}

    r = client.post(api_url, data=parameters, headers=auth)
    if r.ok:
        return int(r.json()["id"])
    else:
        logger.error(
            f"mastodon post: {username}: {r.status_code} {r.reason}\n{status}",
        )
        return None


def repost(post_id, username):
    account = topics.get_account_configuration("mastodon", username)
    access_token = account.get("token")

    if not access_token:
        logger.warning(f"Mastodon bot: {username} non properly configured")
        return None

    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        random.seed()
        print(username)
        print(post_id)
        return post_id

    client = http.client(with_cache=False)

    api_url = f"https://mastodon.social/api/v1/statuses/{post_id}/reblog"

    auth = {"Authorization": f"Bearer {access_token}"}
    parameters = {"id": post_id}

    r = client.post(api_url, data=parameters, headers=auth)
    if r.ok:
        return post_id
    else:
        logger.error(
            f"mastodon post: {username}: {r.status_code} {r.reason} {post_id}",
        )
        return None


def build_hashtags(tags):
    replacements = {"c": "cprogramming"}
    tags = (replacements.get(t, t) for t in tags)
    return sorted(["#" + t for t in tags])


def build_story_post(title=None, url=None, tags=None, author=None, story=None):
    hashtags = build_hashtags(tags)

    if url is None:
        if not title:
            title = story.title
        status = f"""

{story.discussion_url}

{' '.join(hashtags)}"""
    else:
        discussions_url = util.discussions_url(url)

        status = f"""

{url}

Discussions: {discussions_url}

{' '.join(hashtags)}"""

    status = status.rstrip()

    if author and author.mastodon_account:
        status += f"\n\nby @{author.mastodon_account}"
    elif author and author.mastodon_site:
        status += f"\n\nvia @{author.mastodon_site}"

    title = unicodedata.normalize("NFC", title)
    title = "".join(c for c in title if c.isprintable())
    title = " ".join(title.split())
    status = unicodedata.normalize("NFC", status)

    return title + status


def post_story_topic(story, tags, topic, existing_toot):
    if story.story_url:
        resource = models.Resource.by_url(story.story_url)
        author = None
        if resource:
            author = resource.author
        author = author or extract.Author()

        status = build_story_post(story.title, story.story_url, tags, author)
    else:
        status = build_story_post(tags=tags, story=story)

    post_id = None

    bot_name = topic.get("mastodon").get("account")

    try:
        if existing_toot:
            __sleep(35, 47)
            post_id = repost(existing_toot.post_id, bot_name)
        else:
            post_id = post(status, bot_name)
    except Exception as e:
        logger.error(f"mastodon: post: {bot_name}: {e}: {status}: {post_id=}")
        sentry_sdk.capture_exception(e)
        __sleep(13, 27)
        raise

    __sleep(4, 7)

    return post_id


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=0.1)
def post_discussions_scheduled(filter_topic=None):
    __sleep(10, 20)

    five_days_ago = timezone.now() - datetime.timedelta(days=5)
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)

    key_prefix = "mastodon:skip_story:"
    min_comment_count = 2
    min_score = 5

    stories = (
        models.Discussion.objects.filter(created_at__gte=five_days_ago)
        # .filter(comment_count__gte=min_comment_count)
        .filter(score__gte=min_score)
        # .exclude(schemeless_story_url__isnull=True)
        # .exclude(schemeless_story_url="")
        # .exclude(scheme_of_story_url__isnull=True)
        # .exclude(scheme_of_story_url="")
        .order_by("-comment_count", "-score", "created_at")
    )

    logger.debug(f"mastodon scheduled: potential stories {stories.count()}")

    for topic_key, topic in topics.topics.items():
        if not topic.get("mastodon"):
            continue

        if filter_topic and topic_key not in filter_topic:
            continue

        topic_stories = stories

        if topic.get("tags"):
            topic_stories = stories.filter(
                normalized_tags__overlap=list(topic["tags"]),
            )

        topic_stories = topic_stories.exclude(
            mastodonpost__bot_names__contains=[
                topic.get("mastodon").get("account"),
            ],
        )

        logger.debug(
            f"mastodon scheduled: topic {topic_key} potential stories {topic_stories.count()}",
        )

        if topic.get("platform"):
            topic_stories = topic_stories.filter(
                _platform=topic.get("platform"),
            )
            logger.debug(
                f"mastodon scheduled platform {topic.get('platform')}: topic {topic_key} potential stories {topic_stories.count()}",
            )
        else:
            topic_stories = (
                topic_stories.exclude(schemeless_story_url__isnull=True)
                .exclude(schemeless_story_url="")
                .exclude(scheme_of_story_url__isnull=True)
                .exclude(scheme_of_story_url="")
            )

        for story in topic_stories:
            if cache.get(key_prefix + story.platform_id):
                continue

            related_discussions, _, _ = models.Discussion.of_url(
                story.story_url,
                only_relevant_stories=False,
            )

            related_discussions = related_discussions.order_by(
                "-comment_count",
                "-score",
                "created_at",
            )

            if (
                related_discussions.filter(
                    mastodonpost__created_at__gte=seven_days_ago,
                )
                .filter(
                    mastodonpost__bot_names__contains=[
                        topic.get("mastodon").get("account"),
                    ],
                )
                .exists()
            ):
                continue

            existing_post = story.mastodonpost_set.order_by(
                "-created_at",
            ).first()

            tags = set(story.normalized_tags or [])
            for rd in related_discussions[:5]:
                if (
                    rd.comment_count >= min_comment_count
                    and rd.score >= min_score
                ):
                    tags |= set(rd.normalized_tags or [])

                if not existing_post:
                    existing_post = rd.mastodonpost_set.order_by(
                        "-created_at",
                    ).first()

            logger.debug(f"mastodon {story.platform_id}: {tags}")

            post_id = None
            try:
                post_id = post_story_topic(story, tags, topic, existing_post)
            except Exception as e:
                cache.set(
                    key_prefix + story.platform_id,
                    1,
                    timeout=60 * 60 * 5,
                )
                logger.error(f"mastodon: {story.platform_id}: {e}")
                sentry_sdk.capture_exception(e)
                continue

            logger.debug(f"mastodon {topic_key} {post_id} {existing_post}")

            if post_id:
                p = None
                if existing_post:
                    existing_post.bot_names.append(
                        topic.get("mastodon").get("account"),
                    )
                    p = existing_post
                else:
                    p = models.MastodonPost(
                        post_id=post_id,
                        bot_names=[topic.get("mastodon").get("account")],
                    )

                p.save()
                p.discussions.add(story)
                p.save()

            if post_id:
                break


def get_followers_count(usernames):
    cache_timeout = 24 * 60 * 60
    followers_count = {}

    access_token = os.getenv("MASTODON_DISCUSSIONS_ACCESS_TOKEN")

    client = http.client(with_cache=False)

    api_url = "https://mastodon.social/api/v2/search"
    auth = {"Authorization": f"Bearer {access_token}"}
    parameters = {"limit": 5, "resolve": True, "type": "accounts"}

    for username in usernames:
        key = f"mastodon:followers:{username}"
        fc = cache.get(key)
        if fc:
            followers_count[username] = fc
        else:
            parameters["q"] = username
            res = client.get(api_url, params=parameters, headers=auth)

            if not res.ok:
                continue

            for user in res.json()["accounts"]:
                if user["username"].lower() != username:
                    continue

                followers_count[username] = user["followers_count"]
                cache.set(key, user["followers_count"], cache_timeout)

    return followers_count
