import tweepy
import os
from web import util
import logging

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
        print(username)
        print(status)
        print(api_key)
        print(api_secret_key)
        print(token)
        print(token_secret)
        return

    auth = tweepy.OAuthHandler(api_key, api_secret_key)
    auth.set_access_token(token, token_secret)
    api = tweepy.API(auth)
    api.update_status(tweet, wait_on_rate_limit=True)


def __augment_tags(title, tags, keyword, atleast_tags, new_tag=None):
    if atleast_tags:
        if len(tags & atleast_tags) == 0:
            return tags

    if not new_tag:
        new_tag = keyword.lower()

    if new_tag in tags:
        return tags

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

    hashtags = sorted(['#' + t for t in tags])

    discussions_url = util.discussions_url(url)

    status = f"""{title}
{url}

Discussions: {discussions_url}

{' '.join(hashtags)}"""

    for bot_name, cfg in configuration['bots'].items():
        if not cfg['tags'] or cfg['tags'] & tags:
            tweet(status, bot_name)
