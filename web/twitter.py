import datetime
import logging
import os
import random
import time
import unicodedata

import sentry_sdk
import tweepy
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

from . import celery_util, extract, models, topics, util

logger = logging.getLogger(__name__)


def __sleep(a, b):
    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        return
    time.sleep(random.randint(a, b))


def tweet(status, username):
    api_key = os.getenv("TWITTER_ACCESS_API_KEY")
    api_secret_key = os.getenv("TWITTER_ACCESS_API_SECRET_KEY")

    account = topics.get_account_configuration("twitter", username)

    token = account["token"]
    token_secret = account["token_secret"]

    if not api_key or not api_secret_key or not token or not token_secret:
        logger.warn(f"Twitter bot: {username} non properly configured")
        return

    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        random.seed()
        print(username)
        print(status)

        # print(api_key)
        # print(api_secret_key)
        # print(token)
        # print(token_secret)
        return random.randint(1, 1_000_000)

    auth = tweepy.OAuthHandler(api_key, api_secret_key)
    auth.set_access_token(token, token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    status = api.update_status(status)
    # if status.id:
    #    __sleep(5, 9)
    #    api.create_favorite(status.id)
    return status.id


def retweet(tweet_id, username):
    api_key = os.getenv("TWITTER_ACCESS_API_KEY")
    api_secret_key = os.getenv("TWITTER_ACCESS_API_SECRET_KEY")

    account = topics.get_account_configuration("twitter", username)

    token = account["token"]
    token_secret = account["token_secret"]

    if not api_key or not api_secret_key or not token or not token_secret:
        logger.warn(f"Twitter bot: {username} non properly configured")
        return

    if os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true":
        random.seed()
        # print(username)
        # print(tweet_id)
        return tweet_id

    auth = tweepy.OAuthHandler(api_key, api_secret_key)
    auth.set_access_token(token, token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    api.retweet(tweet_id)
    # __sleep(13, 25)
    # api.create_favorite(tweet_id)
    return tweet_id


STATUS_MAX_LENGTH = 280
URL_LENGTH = 23


def build_hashtags(tags):
    replacements = {"c": "cprogramming"}
    tags = (replacements.get(t, t) for t in tags)
    return sorted(["#" + t for t in tags])


def build_story_status(title, url, tags, author):
    hashtags = build_hashtags(tags)

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

    if author.twitter_account:
        status += f"\n\nby @{author.twitter_account}"
        status_len += f"\n\nby @{author.twitter_account}"
    # elif author.twitter_site:
    #     status += f"\n\nvia @{author.twitter_site}"
    #     status_len += f"\n\nvia @{author.twitter_site}"

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


def tweet_story(
    title, url, tags, platforms, already_tweeted_by, comment_count
):
    resource = models.Resource.by_url(url)
    author = None
    if resource:
        author = resource.author
    author = author or extract.Author()

    status = build_story_status(title, url, tags, author)

    tweeted_by = []
    tweet_id = None

    for topic_key, topic in topics.topics.items():
        if not topic.get("twitter"):
            continue
        bot_name = topic.get("twitter").get("account")
        if not bot_name:
            continue

        if bot_name in already_tweeted_by:
            continue

        if (topic.get("tags") and topic["tags"] & tags) or (
            topic.get("platform") and topic.get("platform") in platforms
        ):
            try:
                if tweet_id:
                    __sleep(35, 47)
                    retweet(tweet_id, bot_name)
                    tweeted_by.append(bot_name)
                else:
                    if bot_name in ("HNDiscussions"):
                        if comment_count < 200:
                            continue

                    tweet_id = tweet(status, bot_name)
                    tweeted_by.append(bot_name)
            except tweepy.errors.Forbidden as fe:
                raise fe
            except Exception as e:
                logger.error(
                    f"twitter: tweet: {bot_name}: {e}: {status}: {tweet_id=}"
                )
                sentry_sdk.capture_exception(e)
                __sleep(13, 27)

            __sleep(4, 7)

    return tweet_id, tweeted_by


def tweet_story_topic(story, tags, topic, existing_tweet):
    resource = models.Resource.by_url(story.story_url)
    author = None
    if resource:
        author = resource.author
    author = author or extract.Author()

    status = build_story_status(story.title, story.story_url, tags, author)

    tweet_id = None

    bot_name = topic.get("twitter").get("account")

    try:
        if existing_tweet:
            __sleep(35, 47)
            tweet_id = retweet(existing_tweet.tweet_id, bot_name)
        else:
            tweet_id = tweet(status, bot_name)
    except tweepy.errors.Forbidden as fe:
        raise fe
    except Exception as e:
        logger.error(f"twitter: tweet: {bot_name}: {e}: {status}: {tweet_id=}")
        sentry_sdk.capture_exception(e)
        __sleep(13, 27)

    __sleep(4, 7)

    return tweet_id


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=0.1)
def tweet_discussions():
    __sleep(10, 20)

    three_days_ago = timezone.now() - datetime.timedelta(days=3)
    five_days_ago = timezone.now() - datetime.timedelta(days=5)

    key_prefix = "twitter:skip_story:"
    min_comment_count = 2
    min_score = 5

    stories = (
        models.Discussion.objects.filter(created_at__gte=three_days_ago)
        .filter(comment_count__gte=min_comment_count)
        .filter(score__gte=min_score)
        .exclude(schemeless_story_url__isnull=True)
        .exclude(schemeless_story_url="")
        .exclude(scheme_of_story_url__isnull=True)
        .order_by("created_at")
    )

    logger.debug(f"twitter: potential stories {stories.count()}")

    for story in stories:
        # fixme: skip for now
        if (
            story.canonical_story_url == "google.com"
            or story.canonical_story_url == "google.com/trends/explore"
            or story.canonical_story_url == "asp.net"
            or story.story_url == "https://www.privacytools.io/#photos"
            or story.canonical_story_url == "example.com"
            or story.canonical_story_url == "itch.io"
            or story.canonical_story_url == "crates.io"
            or story.canonical_story_url == "amazon.com"
            or story.canonical_story_url == "github.com"
        ):
            continue

        if cache.get(key_prefix + story.platform_id):
            continue

        related_discussions, _, _ = models.Discussion.of_url(
            story.story_url, only_relevant_stories=False
        )

        total_comment_count = 0
        for rd in related_discussions:
            total_comment_count += rd.comment_count

        if total_comment_count < 10:
            continue

        already_tweeted_by = []

        for t in story.tweet_set.filter(created_at__gte=five_days_ago):
            already_tweeted_by.append(t.bot_name)
            already_tweeted_by.extend(t.bot_names)

        # see if this story was recently tweeted
        for rd in related_discussions:
            for t in rd.tweet_set.filter(created_at__gte=five_days_ago):
                already_tweeted_by.append(t.bot_name)
                already_tweeted_by.extend(t.bot_names)

        already_tweeted_by = set(already_tweeted_by)

        tags = set(story.normalized_tags or [])
        platforms = {story.platform}
        for rd in related_discussions:
            if rd.comment_count >= min_comment_count and rd.score >= min_score:
                tags |= set(rd.normalized_tags or [])
            if (
                rd.comment_count >= min_comment_count
                and rd.score >= min_score
                and rd.created_at >= five_days_ago
            ):

                platforms |= {rd.platform}

        logger.debug(
            f"twitter {story.platform_id}: {already_tweeted_by}: {platforms}: {tags}"
        )

        tweet_id, tweeted_by = None, []
        try:
            tweet_id, tweeted_by = tweet_story(
                story.title,
                story.story_url,
                tags,
                platforms,
                already_tweeted_by,
                story.comment_count,
            )
        except tweepy.errors.Forbidden:
            cache.set(key_prefix + story.platform_id, 1, timeout=60 * 60 * 5)
            continue
        except Exception as e:
            logger.error(f"twitter: {story.platform_id}: {e}")
            sentry_sdk.capture_exception(e)
            continue

        logger.debug(f"twitter {tweet_id}: {tweeted_by}")

        if tweet_id:
            t = models.Tweet(tweet_id=tweet_id, bot_names=tweeted_by)
            t.save()
            t.discussions.add(story)
            t.save()

        if tweet_id:
            break


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=0.1)
def tweet_discussions_scheduled():
    __sleep(10, 20)

    five_days_ago = timezone.now() - datetime.timedelta(days=5)
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)

    key_prefix = "twitter:skip_story:"
    min_comment_count = 2
    min_score = 5

    stories = (
        models.Discussion.objects.filter(created_at__gte=five_days_ago)
        .filter(comment_count__gte=min_comment_count)
        .filter(score__gte=min_score)
        .exclude(schemeless_story_url__isnull=True)
        .exclude(schemeless_story_url="")
        .exclude(scheme_of_story_url__isnull=True)
        .exclude(scheme_of_story_url="")
        .order_by("-comment_count", "-score", "created_at")
    )

    logger.debug(f"twitter scheduled: potential stories {stories.count()}")

    for topic_key, topic in topics.topics.items():
        if not topic.get("twitter"):
            continue

        topic_stories = stories

        if topic.get("tags"):
            topic_stories = stories.filter(
                normalized_tags__overlap=list(topic["tags"])
            )

        topic_stories = topic_stories.exclude(
            tweet__bot_names__contains=[topic.get("twitter").get("account")]
        )

        logger.debug(
            f"twitter scheduled: topic {topic_key} potential stories {topic_stories.count()}"
        )

        if topic.get("platform"):
            topic_stories = topic_stories.filter(
                platform=topic.get("platform")
            )
            logger.debug(
                f"twitter scheduled platform {topic.get('platform')}: topic {topic_key} potential stories {topic_stories.count()}"
            )

        # print(topic_stories.query)

        for story in topic_stories:
            if cache.get(key_prefix + story.platform_id):
                continue

            # if topic_key == "hackernews":
            #     if story.comment_count < 200:
            #         continue

            related_discussions, _, _ = models.Discussion.of_url(
                story.story_url, only_relevant_stories=False
            )

            related_discussions = related_discussions.order_by(
                "-comment_count", "-score", "created_at"
            )

            if (
                related_discussions.filter(
                    tweet__created_at__gte=seven_days_ago
                )
                .filter(
                    tweet__bot_names__contains=[
                        topic.get("twitter").get("account")
                    ]
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
                        "-created_at"
                    ).first()

            logger.debug(f"twitter {story.platform_id}: {tags}")

            tweet_id = None
            try:
                tweet_id = tweet_story_topic(
                    story, tags, topic, existing_tweet
                )
            except tweepy.errors.Forbidden:
                cache.set(
                    key_prefix + story.platform_id, 1, timeout=60 * 60 * 5
                )
                continue
            except Exception as e:
                logger.error(f"twitter: {story.platform_id}: {e}")
                sentry_sdk.capture_exception(e)
                continue

            logger.debug(f"twitter {topic_key} {tweet_id} {existing_tweet}")

            if tweet_id:
                t = None
                if existing_tweet:
                    existing_tweet.bot_names.append(
                        topic.get("twitter").get("account")
                    )
                    t = existing_tweet
                else:
                    t = models.Tweet(
                        tweet_id=tweet_id,
                        bot_names=[topic.get("twitter").get("account")],
                    )

                t.save()
                t.discussions.add(story)
                t.save()

            if tweet_id:
                break


def get_followers_count(usernames):
    followers_count = {}
    auth = tweepy.OAuth2BearerHandler(os.getenv("TWITTER_BEARER_TOKEN"))
    api = tweepy.API(auth)
    for username in usernames:
        try:
            user = api.get_user(screen_name=username)
            followers_count[username] = user.followers_count
        except Exception as e:
            logger.warn(f"twitter followers count: {e}")

    return followers_count
