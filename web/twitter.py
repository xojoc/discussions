import tweepy
import os
from . import util
import logging
from celery import shared_task
from . import models
from django.utils import timezone
import datetime
import random

logger = logging.getLogger(__name__)

# other parameters filled inside web/apps.py
configuration = {
    'bots': {
        'ProgDiscussions': {
            'email': 'programming_discussions@xojoc.pw',
            'tags': {'programming'},
            'description': 'Programming discussions',
            'topic': 'Programming'
        },
        'RustDiscussions': {
            'email': 'rust_discussions@xojoc.pw',
            'user_id': '1446199026865557510',
            'tags': {'rustlang'},
            'description': 'Rust discussions',
            'topic': 'Rust'
        },
        'IntPyDiscu': {
            'email': 'python_discussions@xojoc.pw',
            'user_id': '1442929661328117760',
            'tags': {'python'},
            'description': 'Python discussions',
            'topic': 'Python'
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
        print(api_key)
        print(api_secret_key)
        print(token)
        print(token_secret)
        return random.randint(1, 1_000_000)

    auth = tweepy.OAuthHandler(api_key, api_secret_key)
    auth.set_access_token(token, token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    status = api.update_status(status)
    if status.id:
        api.create_favorite(status.id)
    return status.id


def tweet_story(title, url, tags):
    hashtags = sorted(['#' + t for t in tags])

    discussions_url = util.discussions_url(url)

    status = f"""{title}

{url}

Discussions: {discussions_url}

{' '.join(hashtags)}"""

    tweet_ids = set()

    for bot_name, cfg in configuration['bots'].items():
        if cfg.get('tags') and cfg['tags'] & tags:
            tweet_id = tweet(status, bot_name)
            tweet_ids.add((tweet_id, bot_name))

    return tweet_ids


@shared_task(ignore_result=True)
def tweet_discussions():
    three_days_ago = timezone.now() - datetime.timedelta(days=3)
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
                filter(created_at__gte=three_days_ago).\
                filter(discussions=rd)

            for t in ts:
                t.discussions.add(story)
                t.save()
                already_tweeted = True

        if already_tweeted:
            continue

        tags = set(story.normalized_tags or [])
        for rd in related_discussions:
            tags = tags | set(rd.normalized_tags or [])

        tweet_ids = tweet_story(story.title, story.story_url, tags)

        for tweet_id in tweet_ids:
            t = models.Tweet(tweet_id=tweet_id[0], bot_name=tweet_id[1])
            t.save()
            t.discussions.add(story)
            for rd in related_discussions:
                t.discussions.add(rd)
            t.save()

        if tweet_ids:
            break
