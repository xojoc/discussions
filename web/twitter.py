import tweepy
import os
from . import util
import logging
from celery import shared_task
from . import models, celery_util, extract
from django.utils import timezone
import datetime
import random
import time
import sentry_sdk

logger = logging.getLogger(__name__)

# other parameters filled inside web/apps.py
# order is important: see tweet_story

configuration = {
    'bots': {
        'RustDiscussions': {
            'email': 'rust_discussions@xojoc.pw',
            'user_id': '1446199026865557510',
            'tags': {'rustlang'},
            'description': 'Rust discussions',
            'topic': 'Rust',
            'mastodon_account': '@rust_discussions@mastodon.social',
        },
        'GoDiscussions': {
            'email': 'golang_discussions@xojoc.pw',
            'tags': {'golang'},
            'description': 'Go discussions',
            'topic': 'Golang',
            'mastodon_account': '@golang_discussions@mastodon.social',
        },
        'IntPyDiscu': {
            'email': 'python_discussions@xojoc.pw',
            'user_id': '1442929661328117760',
            'tags': {'python'},
            'description': 'Python discussions',
            'topic': 'Python',
            'mastodon_account': '@python_discussions@mastodon.social',
        },
        'CPPDiscussions': {
            'email': 'c_discussions@xojoc.pw',
            'tags': {'c', 'cpp'},
            'description': 'C & C++ discussions',
            'topic': 'C & C++',
            'mastodon_account': '@c_discussions@mastodon.social',
        },
        'HaskellDiscu': {
            'email': 'haskell_discussions@xojoc.pw',
            'tags': {'haskell'},
            'description': 'Haskell discussions',
            'topic': 'Haskell',
            'mastodon_account': '@haskell_discussions@mastodon.social',
        },
        'LispDiscussions': {
            'email': 'lisp_discussions@xojoc.pw',
            'tags': {'lisp', 'scheme', 'racket'},
            'description': 'Lisp & Scheme discussions',
            'topic': 'Lisp & Scheme',
            'mastodon_account': '@lisp_discussions@mastodon.social',
        },
        'ErlangDiscu': {
            'email': 'erlang_discussions@xojoc.pw',
            'tags': {'erlang', 'elixir'},
            'description': 'Erlang & Elixir discussions',
            'topic': 'Erlang & Elixir',
            'mastodon_account': '@erlang_discussions@mastodon.social',
        },
        'RubyDiscussions': {
            'email': 'ruby_discussions@xojoc.pw',
            'tags': {'ruby'},
            'description': 'Ruby discussions',
            'topic': 'Ruby',
            'mastodon_account': '@ruby_discussions@mastodon.social',
        },
        'CompsciDiscu': {
            'email': 'compsci_discussions@xojoc.pw',
            'tags': {'compsci'},
            'description': 'Computer Science discussions',
            'topic': 'Computer Science',
            'mastodon_account': '@compsci_discussions@mastodon.social',
        },
        'DevopsDiscu': {
            'email': 'devops_discussions@xojoc.pw',
            'tags': {'devops', 'docker', 'kubernets'},
            'description': 'DevOps discussions',
            'topic': 'DevOps',
            'mastodon_account': '@devops_discussions@mastodon.social',
        },
        'ProgDiscussions': {
            'email': 'programming_discussions@xojoc.pw',
            'tags': {'programming'},
            'description': 'Programming discussions',
            'topic': 'Programming',
            'mastodon_account': '@programming_discussions@mastodon.social',
        },
        'HNDiscussions': {
            'email': 'hn_discussions@xojoc.pw',
            'tags': {},
            'description': 'Hacker News discussions',
            'topic': 'Hacker News',
            'platform': 'h',
            'mastodon_account': '@hn_discussions@mastodon.social',
        }
    }
}


def __sleep(a, b):
    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
        return
    time.sleep(random.randint(a, b))


def __print(s):
    # logger.info(s)
    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
        print(s)


def tweet(status, username):
    api_key = configuration['api_key']
    api_secret_key = configuration['api_secret_key']
    token = configuration['bots'][username]['token']
    token_secret = configuration['bots'][username]['token_secret']

    if not api_key or not api_secret_key or not token or not token_secret:
        logger.warn(f"Twitter bot: {username} non properly configured")
        return

    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
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
    api_key = configuration['api_key']
    api_secret_key = configuration['api_secret_key']
    token = configuration['bots'][username]['token']
    token_secret = configuration['bots'][username]['token_secret']

    if not api_key or not api_secret_key or not token or not token_secret:
        logger.warn(f"Twitter bot: {username} non properly configured")
        return

    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
        random.seed()
        print(username)
        print(tweet_id)
        return random.randint(1, 1_000_000)

    auth = tweepy.OAuthHandler(api_key, api_secret_key)
    auth.set_access_token(token, token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    api.retweet(tweet_id)
    # __sleep(13, 25)
    # api.create_favorite(tweet_id)
    return tweet_id


STATUS_MAX_LENGTH = 280
URL_LENGTH = 23


def __hashtags(tags):
    replacements = {'c': 'cprogramming'}
    tags = (replacements.get(t, t) for t in tags)
    return sorted(['#' + t for t in tags])


def build_story_status(title, url, tags, author):
    hashtags = __hashtags(tags)

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
    elif author.twitter_site:
        status += f"\n\nvia @{author.twitter_site}"
        status_len += f"\n\nvia @{author.twitter_site}"

    left_len = STATUS_MAX_LENGTH - len(status_len)

    if len(title) > left_len:
        status = title[:left_len - 2] + "…" + status
    else:
        status = title + status

    return status


def tweet_story(title, url, tags, platforms, already_tweeted_by):
    resource = models.Resource.by_url(url)
    author = None
    if resource:
        author = resource.author
    author = author or extract.Author()

    status = build_story_status(title, url, tags, author)

    tweeted_by = []
    tweet_id = None

    for bot_name, cfg in configuration['bots'].items():
        if bot_name in already_tweeted_by:
            continue

        if (cfg.get('tags') and cfg['tags'] & tags) or \
           (cfg.get('platform') and cfg.get('platform') in platforms):
            if tweet_id:
                try:
                    __sleep(11, 23)
                    retweet(tweet_id, bot_name)
                    tweeted_by.append(bot_name)
                except Exception as e:
                    logger.warn(f"twitter {bot_name}: {e}")
                    sentry_sdk.capture_exception(e)
                    __sleep(7, 13)
            else:
                try:
                    tweet_id = tweet(status, bot_name)
                    tweeted_by.append(bot_name)
                except Exception as e:
                    logger.warn(f"twitter {bot_name}: {e}: {status}")
                    sentry_sdk.capture_exception(e)
                    __sleep(2, 5)

            __sleep(4, 7)

    return tweet_id, tweeted_by


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=0.1)
def tweet_discussions():
    __sleep(10, 20)

    three_days_ago = timezone.now() - datetime.timedelta(days=3)
    five_days_ago = timezone.now() - datetime.timedelta(days=5)

    min_comment_count = 2
    min_score = 5

    stories = models.Discussion.objects.\
        filter(created_at__gte=three_days_ago).\
        filter(comment_count__gte=min_comment_count).\
        filter(score__gte=min_score).\
        exclude(schemeless_story_url__isnull=True).\
        order_by('created_at')

    logger.info(f"twitter: potential stories {stories.count()}")

    for story in stories:
        related_discussions, _, _ = models.Discussion.of_url(
            story.story_url, only_relevant_stories=False)

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
            if rd.comment_count >= min_comment_count and \
               rd.score >= min_score and \
               rd.created_at >= five_days_ago:

                platforms |= {rd.platform}

        logger.info(f"twitter {story.platform_id}: {already_tweeted_by}: {platforms}: {tags}")

        tweet_id = None
        try:
            tweet_id, tweeted_by = tweet_story(
                story.title, story.story_url, tags, platforms, already_tweeted_by)
        except Exception as e:
            logger.warn(f"twitter: {story.platform_id}: {e}")
            sentry_sdk.capture_exception(e)

        logger.info(f"twitter {tweet_id}: {tweeted_by}")

        if tweet_id:
            t = models.Tweet(tweet_id=tweet_id, bot_names=tweeted_by)
            t.save()
            t.discussions.add(story)
            t.save()

        if tweet_id:
            break
