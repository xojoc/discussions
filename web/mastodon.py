import os
from . import util
import logging
from celery import shared_task
from . import models, celery_util, extract, http
from django.utils import timezone
import datetime
import random
import time
import sentry_sdk
from web.twitter import configuration

logger = logging.getLogger(__name__)


def __sleep(a, b):
    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
        return
    time.sleep(random.randint(a, b))


def __print(s):
    # logger.info(s)
    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
        print(s)


def profile_url(account):
    parts = account.split('@')
    return f"https://{parts[2]}/@{parts[1]}"


def post(status, username, post_from_dev=False):
    access_token = configuration['bots'][username].get('mastodon_access_token')

    if not access_token:
        logger.warn(f"Mastodon bot: {username} non properly configured")
        return

    if not post_from_dev:
        if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
            random.seed()
            print(username)
            print(status)
            return random.randint(1, 1_000_000)

    client = http.client(with_cache=False)

    api_url = 'https://mastodon.social/api/v1/statuses'
    auth = {'Authorization': f'Bearer {access_token}'}
    parameters = {'status': status}

    r = client.post(api_url, data=parameters, headers=auth)
    if r.ok:
        return int(r.json()['id'])
    else:
        logger.error(f"mastodon post: {username}: {r.status_code} {r.reason}\n{status}")
        return


def repost(post_id, username):
    access_token = configuration['bots'][username].get('mastodon_access_token')

    if not access_token:
        logger.warn(f"Mastodon bot: {username} non properly configured")
        return

    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
        random.seed()
        print(username)
        print(post_id)
        return post_id

    client = http.client(with_cache=False)

    api_url = f'https://mastodon.social/api/v1/statuses/{post_id}/reblog'

    auth = {'Authorization': f'Bearer {access_token}'}
    parameters = {'id': post_id}

    r = client.post(api_url, data=parameters, headers=auth)
    if r.ok:
        return post_id
    else:
        logger.error(f"mastodon post: {username}: {r.status_code} {r.reason} {post_id}")
        return


def __hashtags(tags):
    replacements = {'c': 'cprogramming'}
    tags = (replacements.get(t, t) for t in tags)
    return sorted(['#' + t for t in tags])


def build_story_post(title, url, tags, author):
    hashtags = __hashtags(tags)

    discussions_url = util.discussions_url(url)

    status = f"""

{url}

Discussions: {discussions_url}

{' '.join(hashtags)}"""

    status = status.rstrip()

    if author.mastodon_account:
        status += f"\n\nby @{author.mastodon_account}"
    elif author.mastodon_site:
        status += f"\n\nvia @{author.mastodon_site}"

    status = title + status

    return status


def post_story(title, url, tags, platforms, already_posted_by):
    resource = models.Resource.by_url(url)
    author = None
    if resource:
        author = resource.author
    author = author or extract.Author()

    status = build_story_post(title, url, tags, author)

    posted_by = []
    post_id = None

    for bot_name, cfg in configuration['bots'].items():
        if bot_name in already_posted_by:
            continue

        if not cfg.get('mastodon_account'):
            continue

        if (cfg.get('tags') and cfg['tags'] & tags) or \
           (cfg.get('platform') and cfg.get('platform') in platforms):
            if post_id:
                try:
                    __sleep(11, 23)
                    repost(post_id, bot_name)
                    posted_by.append(bot_name)
                except Exception as e:
                    logger.warn(f"mastodon {bot_name}: {e}")
                    sentry_sdk.capture_exception(e)
                    __sleep(7, 13)
            else:
                try:
                    post_id = post(status, bot_name)
                    posted_by.append(bot_name)
                except Exception as e:
                    logger.warn(f"mastodon {bot_name}: {e}: {status}")
                    sentry_sdk.capture_exception(e)
                    __sleep(2, 5)

            __sleep(4, 7)

    return post_id, posted_by


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=0.1)
def post_discussions():
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

    for story in stories:
        related_discussions, _, _ = models.Discussion.of_url(
            story.story_url, only_relevant_stories=False)

        total_comment_count = 0
        for rd in related_discussions:
            total_comment_count += rd.comment_count

        if total_comment_count < 10:
            continue

        already_posted_by = []

        for t in story.mastodonpost_set.filter(created_at__gte=five_days_ago):
            already_posted_by.extend(t.bot_names)

        # see if this story was recently posted
        for rd in related_discussions:
            for t in rd.mastodonpost_set.filter(created_at__gte=five_days_ago):
                already_posted_by.extend(t.bot_names)

        already_posted_by = set(already_posted_by)

        tags = set(story.normalized_tags or [])
        platforms = {story.platform}
        for rd in related_discussions:
            if rd.comment_count >= min_comment_count and rd.score >= min_score:
                tags |= set(rd.normalized_tags or [])
            if rd.comment_count >= min_comment_count and \
               rd.score >= min_score and \
               rd.created_at >= five_days_ago:

                platforms |= {rd.platform}

        logger.info(f"mastodon {story.platform_id}: {already_posted_by}: {platforms}")

        post_id = None
        try:
            post_id, posted_by = post_story(
                story.title, story.story_url, tags, platforms, already_posted_by)
        except Exception as e:
            logger.warn(f"mastodon {story.platform_id}: {e}")

        logger.info(f"mastodon {post_id}: {posted_by}")

        if post_id:
            t = models.MastodonPost(post_id=post_id, bot_names=posted_by)
            t.save()
            t.discussions.add(story)
            t.save()

        if post_id:
            break
