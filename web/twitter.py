import tweepy
import os
from . import util
import logging
from celery import shared_task
from . import models
from django.utils import timezone
import datetime
import random
import time

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
            'topic': 'Rust'
        },
        'GoDiscussions': {
            'email': 'golang_discussions@xojoc.pw',
            'tags': {'golang'},
            'description': 'Go discussions',
            'topic': 'Golang'
        },
        'IntPyDiscu': {
            'email': 'python_discussions@xojoc.pw',
            'user_id': '1442929661328117760',
            'tags': {'python'},
            'description': 'Python discussions',
            'topic': 'Python'
        },
        'CPPDiscussions': {
            'email': 'c_discussions@xojoc.pw',
            'tags': {'c', 'cpp'},
            'description': 'C & C++ discussions',
            'topic': 'C & C++'
        },
        'HaskellDiscu': {
            'email': 'haskell_discussions@xojoc.pw',
            'tags': {'haskell'},
            'description': 'Haskell discussions',
            'topic': 'Haskell'
        },
        'LispDiscussions': {
            'email': 'lisp_discussions@xojoc.pw',
            'tags': {'lisp', 'scheme', 'racket'},
            'description': 'Lisp & Scheme discussions',
            'topic': 'Lisp & Scheme'
        },
        'ErlangDiscu': {
            'email': 'erlang_discussions@xojoc.pw',
            'tags': {'erlang', 'elixir'},
            'description': 'Erlang & Elixir discussions',
            'topic': 'Erlang & Elixir'
        },
        'RubyDiscussions': {
            'email': 'ruby_discussions@xojoc.pw',
            'tags': {'ruby'},
            'description': 'Ruby discussions',
            'topic': 'Ruby'
        },
        'CompsciDiscu': {
            'email': 'compsci_discussions@xojoc.pw',
            'tags': {'compsci'},
            'description': 'Computer Science  discussions',
            'topic': 'Computer Science'
        },
        'DevopsDiscu': {
            'email': 'devops_discussions@xojoc.pw',
            'tags': {'devops', 'docker', 'kubernets'},
            'description': 'DevOps discussions',
            'topic': 'DevOps'
        },
        'ProgDiscussions': {
            'email': 'programming_discussions@xojoc.pw',
            'tags': {'programming'},
            'description': 'Programming discussions',
            'topic': 'Programming'
        },
        'HNDiscussions': {
            'email': 'hn_discussions@xojoc.pw',
            'tags': {},
            'description': 'Hacker News discussions',
            'topic': 'Hacker News',
            'platform': 'h'
        }
    }
}


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
    if status.id:
        api.create_favorite(status.id)
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
    api.create_favorite(tweet_id)
    return tweet_id


STATUS_MAX_LENGTH = 280
URL_LENGTH = 23


def __hashtags(tags):
    replacements = {'c': 'cprogramming'}
    tags = (replacements.get(t, t) for t in tags)
    return sorted(['#' + t for t in tags])


def build_story_status(title, url, tags):
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

    left_len = STATUS_MAX_LENGTH - len(status_len)

    if len(title) > left_len:
        status = title[:left_len - 2] + "…" + status
    else:
        status = title + status

    return status


def tweet_story(title, url, tags, platform, already_tweeted):
    status = build_story_status(title, url, tags)

    tweet_ids = set()

    tweet_id = None

    for bot_name, cfg in configuration['bots'].items():
        if (not already_tweeted and cfg.get('tags') and cfg['tags'] & tags) or cfg.get('platform') == platform:
            if tweet_id:
                try:
                    retweet(tweet_id, bot_name)
                except Exception as e:
                    logger.warn(f"{bot_name}: {e}")
                    time.sleep(3)
            else:
                try:
                    tweet_id = tweet(status, bot_name)
                    tweet_ids.add((tweet_id, bot_name))
                except Exception as e:
                    logger.warn(f"{bot_name}: {e}")
                    time.sleep(3)
            time.sleep(2)

    return tweet_ids


@shared_task(ignore_result=True)
def tweet_discussions():
    three_days_ago = timezone.now() - datetime.timedelta(days=3)
    five_days_ago = timezone.now() - datetime.timedelta(days=5)
    stories = models.Discussion.objects.\
        filter(created_at__gte=three_days_ago).\
        filter(comment_count__gte=1).\
        filter(score__gte=2).\
        filter(tweet=None)

    for story in stories:
        related_discussions, _, _ = models.Discussion.of_url(
            story.story_url, only_relevant_stories=False)

        total_comment_count = 0
        # total_comment_count += story.comment_count
        for rd in related_discussions:
            total_comment_count += rd.comment_count

        if total_comment_count < 10:
            continue

        already_tweeted = False

        # see if this story was recently tweeted
        for rd in related_discussions:
            ts = models.Tweet.objects.\
                filter(created_at__gte=five_days_ago).\
                filter(discussions=rd)

            for t in ts:
                t.discussions.add(story)
                t.save()
                already_tweeted = True

        # if already_tweeted:
        #     continue

        tags = set(story.normalized_tags or [])
        for rd in related_discussions:
            tags = tags | set(rd.normalized_tags or [])

        tweet_ids = []
        try:
            tweet_ids = tweet_story(
                story.title, story.story_url, tags, story.platform, already_tweeted)
        except Exception as e:
            logger.warn(e)

        for tweet_id in tweet_ids:
            t = models.Tweet(tweet_id=tweet_id[0], bot_name=tweet_id[1])
            t.save()
            t.discussions.add(story)
            for rd in related_discussions:
                t.discussions.add(rd)
            t.save()

        if tweet_ids:
            break
