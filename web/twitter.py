# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import logging
import os
import random
import time
import unicodedata

import sentry_sdk
import tweepy
import tweepy.client
import tweepy.errors
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from typing_extensions import override

from . import celery_util, extract, models, topics, util

logger = logging.getLogger(__name__)


def __sleep(a, b):
    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        return
    time.sleep(random.randint(a, b))  # noqa: S311


def tweet(status, username):
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")

    account = topics.get_account_configuration("twitter", username)
    if not account:
        return None

    token = account.get("token")
    token_secret = account.get("token_secret")

    if (
        not consumer_key
        or not consumer_secret
        or not token
        or not token_secret
    ):
        logger.warning(f"Twitter bot: {username} non properly configured")
        if not consumer_key:
            logger.warning("consumer_key")
        if not consumer_secret:
            logger.warning("consumer_secret")
        if not token:
            logger.warning("token")
        if not token_secret:
            logger.warning("token_secret")
        return None

    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        random.seed()
        print(username)  # noqa: T201
        print(status)  # noqa: T201

        return random.randint(1, 1_000_000)  # noqa: S311

    api = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=token,
        access_token_secret=token_secret,
        wait_on_rate_limit=False,
    )
    status = api.create_tweet(text=status)

    if not isinstance(status, tweepy.client.Response):
        return None

    return status.data["id"]


# TODO: for now we cannot retweet, upgrade?
def retweet(tweet_id, username):
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")

    account = topics.get_account_configuration("twitter", username)
    if not account:
        return None
    token = account["token"]
    token_secret = account["token_secret"]

    if (
        not consumer_key
        or not consumer_secret
        or not token
        or not token_secret
    ):
        logger.warning(f"Twitter bot: {username} non properly configured")
        return None

    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        return tweet_id

    api = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=token,
        access_token_secret=token_secret,
        wait_on_rate_limit=True,
    )
    _ = api.retweet(tweet_id)
    return tweet_id


STATUS_MAX_LENGTH = 280
URL_LENGTH = 23


def build_hashtags(tags):
    replacements = {"c": "cprogramming"}
    tags = (replacements.get(t, t) for t in tags)
    return sorted(["#" + t for t in tags])


def build_story_status(
    title: str = "",
    url: str | None = "",
    tags: set[str] | None = None,
    author: extract.Author | None = None,
    story: models.Discussion | None = None,
) -> str:
    tags = tags or set()
    if not tags and story:
        tags = set(story.normalized_tags)
    hashtags = build_hashtags(tags)

    if not url and story:
        if not title:
            title = story.title

        status = f"""

{story.discussion_url}

{' '.join(hashtags)}"""

        status_len = f"""

{'x' * URL_LENGTH}

{' '.join(hashtags)}"""
    else:
        discussions_url = util.discussions_url(url)

        status = f"""

{url}

Discussions: {discussions_url}

{' '.join(hashtags)}"""

        status_len = f"""

{'x' * URL_LENGTH}

Discussions: {'x' * URL_LENGTH}

{' '.join(hashtags)}"""

    status = status.rstrip()
    status_len = status_len.rstrip()

    if author and author.twitter_account:
        status += f"\n\nby @{author.twitter_account}"
        status_len += f"\n\nby @{author.twitter_account}"

    title = unicodedata.normalize("NFC", title)
    title = "".join(c for c in title if c.isprintable())
    title = " ".join(title.split())
    status = unicodedata.normalize("NFC", status)
    status_len = unicodedata.normalize("NFC", status_len)

    left_len = STATUS_MAX_LENGTH - len(status_len)

    if len(title) > left_len:
        status = title[: left_len - 2] + "…" + status
    else:
        status = title + status

    return status


def tweet_story_topic(story, tags, topic, existing_tweet):
    if story.story_url:
        resource = models.Resource.by_url(story.story_url)
        author = None
        if resource:
            author = resource.author
        author = author or extract.Author()

        status = build_story_status(story.title, story.story_url, tags, author)
    else:
        status = build_story_status(tags=tags, story=story)

    tweet_id = None

    bot_name = topic.get("twitter").get("account")

    try:
        if existing_tweet:
            __sleep(35, 47)
            tweet_id = tweet(status, bot_name)
        else:
            tweet_id = tweet(status, bot_name)
    except tweepy.errors.Forbidden:
        raise
    except tweepy.errors.TooManyRequests:
        raise
    except Exception as e:
        logger.exception(
            f"twitter v2: tweet: {bot_name}: {status}: {tweet_id=}",
        )
        _ = sentry_sdk.capture_exception(e)
        __sleep(13, 27)

    __sleep(4, 7)

    return tweet_id


@shared_task(bind=True, ignore_result=True)
def tweet_discussions_scheduled(self, filter_topic=None):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    __sleep(10, 20)

    five_days_ago = timezone.now() - datetime.timedelta(days=5)
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)

    key_prefix = "twitter:skip_story:"
    min_comment_count = 2
    min_score = 5

    stories = (
        models.Discussion.objects.filter(created_at__gte=five_days_ago)
        .filter(score__gte=min_score)
        .order_by("-comment_count", "-score", "created_at")
    )

    logger.debug(f"twitter scheduled: potential stories {stories.count()}")

    for topic_key, topic in topics.topics.items():
        if not topic.get("twitter"):
            continue

        if filter_topic and topic_key not in filter_topic:
            continue

        topic_stories = stories

        if topic.get("tags"):
            topic_stories = stories.filter(
                normalized_tags__overlap=list(topic["tags"]),
            )

        topic_stories = topic_stories.exclude(
            tweet__bot_names__contains=[topic.get("twitter").get("account")],
        )

        logger.debug(
            f"twitter scheduled: topic {topic_key} potential stories {topic_stories.count()}",
        )

        if topic.get("platform"):
            topic_stories = topic_stories.filter(
                _platform=topic.get("platform"),
            )
            logger.debug(
                f"twitter scheduled platform {topic.get('platform')}: topic {topic_key} potential stories {topic_stories.count()}",
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
                    tweet__created_at__gte=seven_days_ago,
                )
                .filter(
                    tweet__bot_names__contains=[
                        topic.get("twitter").get("account"),
                    ],
                )
                .exists()
            ):
                continue

            existing_tweet = story.tweet_set.order_by("-created_at").first()

            tags = set(story.normalized_tags or [])
            for rd in related_discussions[:5]:
                if (
                    rd.comment_count >= min_comment_count
                    and rd.score >= min_score
                ):
                    tags |= set(rd.normalized_tags or [])

                if not existing_tweet:
                    existing_tweet = rd.tweet_set.order_by(
                        "-created_at",
                    ).first()

            logger.debug(f"twitter {story.platform_id}: {tags}")

            tweet_id = None
            try:
                tweet_id = tweet_story_topic(
                    story,
                    tags,
                    topic,
                    existing_tweet,
                )
            except tweepy.errors.Forbidden:
                cache.set(
                    key_prefix + story.platform_id,
                    1,
                    timeout=60 * 60 * 5,
                )
                continue
            except tweepy.errors.TooManyRequests as e:
                logger.exception(
                    f"twitter too many requests, interrupt {topic_key}",
                )
                _ = sentry_sdk.capture_exception(e)
                __sleep(10, 20)
                break
            except Exception as e:
                logger.exception(f"twitter: {story.platform_id}")
                _ = sentry_sdk.capture_exception(e)
                continue

            logger.debug(f"twitter {topic_key} {tweet_id} {existing_tweet}")

            if tweet_id:
                t = None
                if existing_tweet:
                    existing_tweet.bot_names.append(
                        topic.get("twitter").get("account"),
                    )
                    t = existing_tweet
                else:
                    t = models.Tweet(
                        tweet_id=tweet_id,
                        bot_names=[topic.get("twitter").get("account")],
                    )

                _ = t.save()
                _ = t.discussions.add(story)
                _ = t.save()

            if tweet_id:
                break


def client():
    return tweepy.Client(os.getenv("TWITTER_BEARER_TOKEN"))


class IDPrinter(tweepy.StreamingClient):
    @override
    def on_tweet(self, tweet):
        logger.debug(tweet.id)
        logger.debug(tweet.text)


def __build_twitter_rule():
    r = "lang:en -is:retweet -is:reply -is:quote -is:nullcast has:links followers_count:10000"
    r += " ("
    context_computer_programming = "context:131.848921413196984320"
    r += context_computer_programming

    tags = set()

    for t in topics.topics.values():
        tags.update(t.get("tags", set()))

    tags_str = " OR ".join(build_hashtags(tags))

    r += f" OR {tags_str}"

    r += ")"

    return r


def stream(*, reset_filters=False):
    printer = IDPrinter(
        os.getenv("TWITTER_BEARER_TOKEN"),
        wait_on_rate_limit=True,
        chunk_size=1024**2,
        max_retries=3,
    )
    if reset_filters:
        _ = printer.delete_rules(r.id for r in printer.get_rules().data)
        r = __build_twitter_rule()
        logger.info(f"twitter stream: {r}")
        _ = printer.add_rules(tweepy.StreamRule(r))

    logger.debug(f"twitter stream: {printer.get_rules()}")

    _ = printer.filter(tweet_fields="id,text,created_at,entities")


def print_details(tweet_id):
    logger.debug(tweet_id)
    c = client()
    t = c.get_tweet(tweet_id, tweet_fields="context_annotations,entities")
    if not t.data:
        return
    for ca in t.data.context_annotations:
        logger.debug(f"{ca['domain']['id']} - {ca['domain']['name']}")
        logger.debug(f"{ca['entity']['id']} - {ca['entity']['name']}")


def fetch_all_tweets():
    c = client()

    twitter_bots = []
    # for t in topics.topics.values():
    #     if t.get("twitter") and t.get("twitter").get("account"):
    #         u = twitter_api.get_(t.get("twitter").get("account"))
    #         if u and u.get("id"):
    #             twitter_bots.append(u.get("id"))

    users_to_search = []
    for bot in twitter_bots:
        for fs in tweepy.Paginator(
            c.get_users_following,
            bot,
            user_fields="id",
            max_results=1000,
        ):
            users_to_search.extend(u.id for u in fs.data)

    logger.debug(users_to_search)
