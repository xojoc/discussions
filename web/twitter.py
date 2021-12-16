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
        'IntPyDiscu': {
            'email': 'python_discussions@xojoc.pw',
            'user_id': '1442929661328117760',
            'tags': {'python', 'django', 'flask'}
        },
        'RustDiscussions': {
            'email': 'rust_discussions@xojoc.pw',
            'user_id': '1446199026865557510',
            'tags': {'rustlang'}
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


def __augment_tags(title, tags, keyword, atleast_tags, new_tag=None):
    if atleast_tags:
        if len(tags & atleast_tags) == 0:
            return tags

    if not new_tag and keyword:
        new_tag = keyword.lower()

    if not new_tag:
        return tags

    if new_tag in tags:
        return tags

    if keyword:
        if keyword.lower() not in title.lower().split(' '):
            return tags

    return tags | {new_tag}


def __replace_tag(tags, old_tag, new_tag):
    if old_tag not in tags:
        return tags

    return (tags - {old_tag}) | {new_tag}


def tweet_story(title, url, tags):
    if not tags:
        tags = set()
    else:
        tags = set(tags)

    tags = __augment_tags(title, tags, 'django',
                          {'python', 'web', 'webdev', 'programming'})
    tags = __augment_tags(title, tags, 'flask',
                          {'python', 'web', 'webdev', 'programming'})

    tags = __replace_tag(tags, 'rust', 'rustlang')
    tags = __replace_tag(tags, 'go', 'golang')

    tags = __augment_tags(title, tags, None,
                          {'python', 'rustlang', 'golang', 'haskell', 'cpp'},
                          'programming')

    hashtags = sorted(['#' + t for t in tags])

    discussions_url = util.discussions_url(url)

    status = f"""{title}

{url}

Discussions: {discussions_url}

{' '.join(hashtags)}"""

    tweet_ids = set()

    for bot_name, cfg in configuration['bots'].items():
        if not cfg['tags'] or cfg['tags'] & tags:
            tweet_id = tweet(status, bot_name)
            tweet_ids.add((tweet_id, bot_name))

    return tweet_ids


@shared_task(ignore_result=True)
def tweet_discussions():
    three_days_ago = timezone.now() - datetime.timedelta(days=3)
    stories = models.Discussion.objects.\
        filter(created_at__gte=three_days_ago).\
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

        tags = set(story.tags or [])
        for rd in related_discussions:
            tags = tags | set(rd.tags or [])

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
