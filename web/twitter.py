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
    time.sleep(random.randint(a, b))  # noqa: S311


def tweet(status, username):
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")

    account = topics.get_account_configuration("twitter", username)

    token = account["token"]
    token_secret = account["token_secret"]

    if not consumer_key or not consumer_secret or not token or not token_secret:
        logger.warning(f"Twitter bot: {username} non properly configured")
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
        wait_on_rate_limit=True,
    )
    status = api.create_tweet(text=status)

    if not isinstance(status, tweepy.client.Response):
        return None

    return status.data["id"]


# fixme: for now we cannot retweet, upgrade?
def retweet(tweet_id, username):
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")

    account = topics.get_account_configuration("twitter", username)

    token = account["token"]
    token_secret = account["token_secret"]

    if not consumer_key or not consumer_secret or not token or not token_secret:
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
    api.retweet(tweet_id)
    return tweet_id


STATUS_MAX_LENGTH = 280
URL_LENGTH = 23


def build_hashtags(tags):
    replacements = {"c": "cprogramming"}
    tags = (replacements.get(t, t) for t in tags)
    return sorted(["#" + t for t in tags])


def build_story_status(
    title=None,
    url=None,
    tags=None,
    author=None,
    story=None,
):
    tags = tags or set()
    hashtags = build_hashtags(tags)

    if url is None:
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
            # tweet_id = retweet(existing_tweet.tweet_id, bot_name)
            tweet_id = tweet(status, bot_name)
        else:
            tweet_id = tweet(status, bot_name)
    except tweepy.errors.Forbidden:
        raise
    except Exception as e:
        logger.exception(f"twitter: tweet: {bot_name}: {status}: {tweet_id=}")
        sentry_sdk.capture_exception(e)
        __sleep(13, 27)

    __sleep(4, 7)

    return tweet_id


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=0.1)
def tweet_discussions_scheduled(filter_topic=None):
    __sleep(10, 20)

    five_days_ago = timezone.now() - datetime.timedelta(days=5)
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)

    key_prefix = "twitter:skip_story:"
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
                platform=topic.get("platform"),
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
                if rd.comment_count >= min_comment_count and rd.score >= min_score:
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
            except Exception as e:
                logger.exception(f"twitter: {story.platform_id}")
                sentry_sdk.capture_exception(e)
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

                t.save()
                t.discussions.add(story)
                t.save()

            if tweet_id:
                break


def client():
    return tweepy.Client(os.getenv("TWITTER_BEARER_TOKEN"))


def get_user(username, c=None):
    cache_timeout = 60 * 60 * 24
    key = f"twitter:username:{username}"
    user = cache.get(key)
    if user:
        return user

    if not c:
        c = client()

    try:
        user = c.get_user(username=username)
    except Exception as e:
        logger.warning(f"twitter get_user: {e}")
        return None

    user = {
        "id": user.data.id,
        "name": user.data.name,
        "username": user.data.username,
    }

    cache.set(key, user, cache_timeout)

    return user


def get_followers_count(usernames):
    cache_timeout = 24 * 60 * 60
    followers_count = {}
    auth = tweepy.OAuth2BearerHandler(os.getenv("TWITTER_BEARER_TOKEN"))
    api = tweepy.API(auth)

    for username in usernames:
        key = f"twitter:followers:{username}"
        fc = cache.get(key)
        if fc:
            followers_count[username] = fc
        else:
            try:
                user = api.get_user(screen_name=username)
                followers_count[username] = user.followers_count
                cache.set(key, user.followers_count, cache_timeout)
            except Exception as e:
                logger.warning(f"twitter followers count: {e}")

    return followers_count


class IDPrinter(tweepy.StreamingClient):
    def on_tweet(self, tweet):
        print(tweet.id)
        print(tweet.text)
        print()


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


def stream(reset_filters=False):
    printer = IDPrinter(
        os.getenv("TWITTER_BEARER_TOKEN"),
        wait_on_rate_limit=True,
        chunk_size=1024**2,
        max_retries=3,
    )
    if reset_filters:
        printer.delete_rules(r.id for r in printer.get_rules().data)
        r = __build_twitter_rule()
        logger.info(f"twitter stream: {r}")
        printer.add_rules(tweepy.StreamRule(r))

    print(f"twitter stream: {printer.get_rules()}")

    printer.filter(tweet_fields="id,text,created_at,entities")


def print_details(id):
    c = client()
    t = c.get_tweet(id, tweet_fields="context_annotations,entities")
    print(id)
    for ca in t.data.context_annotations:
        print(f"{ca['domain']['id']} - {ca['domain']['name']}")
        print(f"{ca['entity']['id']} - {ca['entity']['name']}")


def process_item(tweet):
    return


def fetch_all_tweets():
    c = client()

    twitter_bots = []
    for t in topics.topics.values():
        if t.get("twitter") and t.get("twitter").get("account"):
            u = get_user(t.get("twitter").get("account"))
            if u and u.get("id"):
                twitter_bots.append(u.get("id"))

    users_to_search = []
    for bot in twitter_bots:
        for fs in tweepy.Paginator(
            c.get_users_following,
            bot,
            user_fields="id",
            max_results=1000,
        ):
            users_to_search.extend(u.id for u in fs.data)

    print(users_to_search)
