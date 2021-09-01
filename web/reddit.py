import bz2
import datetime
import io
import json
import logging
import lzma
import os
import re
import shutil
import time

import praw
import prawcore
import zstandard
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils.timezone import make_aware
from django_redis import get_redis_connection
from discussions.settings import APP_CELERY_TASK_MAX_TIME

from web import celery_util
from . import http, models, discussions
import pickle

logger = logging.getLogger(__name__)

# filled in apps.WebConfig.ready
subreddit_blacklist = set()
subreddit_whitelist = set()


class EndOfSubreddits(Exception):
    pass


def client(with_cache=False, with_retries=True):
    c = praw.Reddit(client_id=settings.REDDIT_CLIENT_ID,
                    client_secret=settings.REDDIT_CLIENT_SECRET,
                    user_agent=settings.USERAGENT,
                    requestor_kwargs={'session': http.client(with_cache=with_cache, with_retries=with_retries)})
    return c


def subreddit(subreddit, listing='new', listing_argument=''):
    redis_client = get_redis_connection("default")
    subreddit = subreddit.lower()
    redis_key = f'discussions:subreddit_cache:{listing}:{listing_argument}:{subreddit}'

    stories = set()
    for story in redis_client.smembers(redis_key):
        stories.add(pickle.loads(story, encoding='UTF-8'))
    if stories:
        return stories

    reddit_client = client()
    list = None
    if listing == 'new':
        list = reddit_client.subreddit(subreddit).new(limit=50)
    if listing == 'top':
        list = reddit_client.subreddit(subreddit).top(
            listing_argument, limit=30)

    for story in list:
        _ = story.title  # force load
        redis_client.sadd(redis_key, pickle.dumps(story))
        stories.add(story)

    redis_client.expire(redis_key, 60 * 9)

    return stories


def get_reddit_archive_links(client, starting_from=None):
    url_prefix = 'https://files.pushshift.io/reddit/submissions/'
    digests = client.get(url_prefix + 'sha256sums.txt')
    available_files = []
    for line in digests.content.decode().split("\n"):
        fields = line.split()
        if len(fields) >= 2:
            available_files.append(fields[1])
    available_months = set()
    for file in available_files:
        match = re.findall(r"RS.*(\d\d\d\d)-(\d\d)\..*", file)[0]
        available_months.add(match[0] + "-" + match[1])

    extensions = ['zst', 'xz', 'bz2']

    chosen_files = []
    for month in sorted(available_months):
        if starting_from and month < starting_from:
            continue
        found = False
        for ext in extensions:
            if found:
                break
            for file in available_files:
                if re.findall(f'RS.*{month}.' + ext, file):
                    found = True
                    chosen_files.append(url_prefix + file)
                    break

    return chosen_files


def url_blacklisted(url):
    if url.startswith('i.imgur.com') or \
            url.startswith('imgur.com') or \
            url.startswith('gfycat.com'):
        return True

    return False


def process_archive_line(line):
    p = json.loads(line)
    if p.get('subreddit') not in subreddit_whitelist:
        print(f"subreddit skipped {p.get('subreddit')}")
        return

    if not p.get('url'):
        return
    if p.get('is_self'):
        return
    if p.get('over_18'):
        return
    if p.get('is_reddit_media_domain'):
        return
    if p.get('hidden'):
        return
    if p.get('media'):
        return
    if p.get('score') < 0 and p.get('num_comments') == 0:
        return

    platform_id = 'r' + p.get('id')

    if models.Discussion.objects.filter(platform_id=platform_id).exists():
        return

    scheme, url = discussions.split_scheme((p.get('url') or '').strip())
    if len(url) > 2000:
        return
    if not scheme:
        logging.warn(
            f"Reddit archive: no scheme for {platform_id}, url {p.get('url')}")
        return

    canonical_url = discussions.canonical_url(url)
    if len(canonical_url) > 2000 or canonical_url == url:
        canonical_url = None

    if url_blacklisted(canonical_url or url):
        return

    created_utc = p.get('created_utc')
    if type(created_utc) == str:
        created_utc = int(created_utc)
    created_at = datetime.datetime.fromtimestamp(created_utc)
    created_at = make_aware(created_at)

    subreddit = p.get('subreddit') or ''

    try:
        models.Discussion(
            platform_id=platform_id,
            comment_count=p.get('num_comments') or 0,
            score=p.get('score') or 0,
            created_at=created_at,
            scheme_of_story_url=scheme,
            schemeless_story_url=url,
            canonical_story_url=canonical_url,
            title=p.get('title'),
            tags=[subreddit.lower()]).save()
    except Exception as e:
        logger.warn(f"Reddit archive: {e}")
        return


def fetch_reddit_archive():
    client = http.client(with_cache=False)
    r = get_redis_connection("default")
    redis_prefix = 'discussions:fetch_reddit_archive'

    for file in get_reddit_archive_links(client):
        logger.warning(f"reddit archive: processing {file}")
        if r.get(f"{redis_prefix}:processed:{file}"):
            continue

        file_name = '/tmp/discussions_reddit_archive_compressed'

        if not r.get(f"{redis_prefix}:downloaded:{file}"):
            with client.get(file, stream=True) as res:
                logger.warning(f"reddit archive: start download {file}")
                f = open(file_name, 'wb')
                shutil.copyfileobj(res.raw, f)
                f.close()
                logger.warning(f"reddit archive: end download {file}")
                r.set(f"{redis_prefix}:downloaded:{file}",
                      1, ex=60 * 60 * 24 * 7)

        f = open(file_name, 'rb')

        if file.endswith('.zst'):
            stream = zstandard.ZstdDecompressor(
                max_window_size=2**31
            ).\
                stream_reader(f, read_across_frames=True)
        if file.endswith('.xz'):
            stream = lzma.open(f, mode="r")
        if file.endswith('.bz2'):
            stream = bz2.open(f, mode="r")

        text = io.TextIOWrapper(stream)

        c = 0
        for line in text:
            if c % 1_000_000 == 0:
                logger.warning(f"reddit archive: File {file}, line {c}")
            c += 1
            try:
                process_archive_line(line)
            except Exception as e:
                logger.warning(f"reddit archive: line failed: {e}")
                logger.warning(line)

        f.close()
        os.remove(file_name)

        r.set(f"{redis_prefix}:processed:{file}", 1, ex=60 * 60 * 24 * 7)

        time.sleep(3)


def fetch_discussions(index):
    reddit = client()
    redis = get_redis_connection("default")
    skip_key_prefix = 'discussions:reddit:skip:'
    temporary_skip_key_prefix = 'discussions:reddit:temporary_skip:'
    skip_sub_key_prefix = 'discussions:reddit:subreddit:skip:'
    max_created_at_key = 'discussions:reddit:max_created_at:'
    cache_timeout = 60 * 30

    start_time = time.monotonic()

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        if index >= len(subreddit_whitelist):
            raise EndOfSubreddits
        subreddit = list(subreddit_whitelist)[index]
        name = subreddit.lower()
        index += 1

        if redis.get(skip_sub_key_prefix + name):
            continue

        limit_new = 50
        try:
            stories = reddit.subreddit(name).new(limit=limit_new)
        except Exception as e:
            logger.log(f"reddit.subreddit({name}): {e}")
            continue

        subreddit_max_created_at = redis.get(max_created_at_key + name)
        max_created_at = 0

        try:
            for p in stories:
                platform_id = f"r{p.id}"

                if redis.get(skip_key_prefix + p.id):
                    redis.set(skip_key_prefix + p.id, 1, ex=cache_timeout)
                    continue

                if redis.get(temporary_skip_key_prefix + p.id):
                    continue

                if not p.url:
                    redis.set(skip_key_prefix + p.id, 1, ex=cache_timeout)
                    continue

                if p.is_self:
                    redis.set(skip_key_prefix + p.id, 1, ex=cache_timeout)
                    continue

                if p.over_18:
                    redis.set(skip_key_prefix + p.id, 1, ex=cache_timeout)
                    continue

                if p.is_reddit_media_domain:
                    redis.set(skip_key_prefix + p.id, 1, ex=cache_timeout)
                    continue

                if p.hidden:
                    redis.set(temporary_skip_key_prefix +
                              p.id, 1, ex=cache_timeout)
                    continue

                if p.media:
                    redis.set(skip_key_prefix + p.id, 1, ex=cache_timeout)
                    continue

                scheme, url = discussions.split_scheme((p.url or '').strip())
                if len(url) > 2000:
                    continue
                if not scheme:
                    redis.set(skip_key_prefix + p.id, 1, ex=cache_timeout)
                    continue

                canonical_url = discussions.canonical_url(url)
                if len(canonical_url) > 2000 or canonical_url == url:
                    canonical_url = None

                if url_blacklisted(canonical_url or url):
                    redis.set(skip_key_prefix + p.id, 1, ex=cache_timeout)
                    continue

                created_utc = p.created_utc
                if type(created_utc) == str:
                    created_utc = int(created_utc)
                created_at = datetime.datetime.fromtimestamp(created_utc)
                created_at = make_aware(created_at)

                max_created_at = max(p.created_utc, max_created_at)

                try:
                    discussion = models.Discussion.objects.get(
                        pk=platform_id)
                    discussion.comment_count = p.num_comments or 0
                    discussion.score = p.score or 0
                    discussion.created_at = created_at
                    discussion.scheme_of_story_url = scheme
                    discussion.schemeless_story_url = url
                    discussion.canonical_story_url = canonical_url
                    discussion.title = p.title
                    discussion.archived = p.archived
                    discussion.tags = [name]
                    discussion.save()
                except models.Discussion.DoesNotExist:
                    models.Discussion(
                        platform_id=platform_id,
                        comment_count=p.num_comments or 0,
                        score=p.score or 0,
                        created_at=created_at,
                        scheme_of_story_url=scheme,
                        schemeless_story_url=url,
                        canonical_story_url=canonical_url,
                        title=p.title,
                        archived=p.archived,
                        tags=[name]).save()

                # To avoid to hit the Reddit API too often, skip this discussion for some time
                redis.set(temporary_skip_key_prefix + p.id, 1, ex=60*15)

        except (prawcore.exceptions.Forbidden,
                prawcore.exceptions.NotFound,
                prawcore.exceptions.PrawcoreException) as e:
            logger.warn(e)
            continue

        if not subreddit_max_created_at or max_created_at > float(subreddit_max_created_at):
            redis.set(max_created_at_key + name,
                      max_created_at, ex=60 * 60 * 24 * 180)
        else:
            # No new story. Skip this subreddit for a while
            redis.set(skip_sub_key_prefix + name, 1,
                      ex=60 * 60)

    return index


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_recent_discussions():
    r = get_redis_connection("default")
    redis_prefix = 'discussions:fetch_recent_reddit_discussions:'
    current_index = int(r.get(redis_prefix + 'current_index') or 0)
    max_index = int(r.get(redis_prefix + 'max_index') or 0)
    if current_index is None or not max_index or (current_index > max_index):
        max_index = len(subreddit_whitelist)
        r.set(redis_prefix + 'max_index', max_index)
        current_index = 0

    try:
        current_index = fetch_discussions(current_index)
    except EndOfSubreddits:
        current_index = max_index + 1

    r.set(redis_prefix + 'current_index', current_index)


def udpate_all_discussions_queryset():
    return (models.Discussion.objects
            .filter(platform='r')
            .filter(archived=False)
            .order_by('pk'))


@transaction.atomic
def update_all_discussions(from_index, to_index):
    reddit = client()

    ps = []
    ds = []

    for d in udpate_all_discussions_queryset()[from_index:to_index].iterator():
        if d.subreddit.lower() in subreddit_blacklist:
            d.delete()
            continue
        if url_blacklisted(d.story_canonical_url or d.schemeless_story_url):
            d.delete()
            continue

        if d.subreddit not in subreddit_whitelist:
            d.delete()
            continue

        ps.append(f't3_{d.id}')
        ds.append(d)

    for p in reddit.info(ps):
        d = next(d for d in ds if d.platform_id and d.id == p.id)

        if p.over_18:
            d.delete()
            continue

        scheme, url = discussions.split_scheme((p.url or '').strip())
        if len(url) > 2000:
            continue
        if not scheme:
            logger.warn(
                f"update_all_stories: no scheme for {p.id}, url {p.url}")
            d.delete()
            continue

        canonical_url = discussions.canonical_url(url)
        if len(canonical_url) > 2000 or canonical_url == url:
            canonical_url = None

        if url_blacklisted(canonical_url or url):
            d.delete()
            continue

        created_utc = p.created_utc
        if type(created_utc) == str:
            created_utc = int(created_utc)
        created_at = datetime.datetime.fromtimestamp(created_utc)
        created_at = make_aware(created_at)

        d.comment_count = p.num_comments or 0
        d.score = p.score or 0
        d.created_at = created_at
        d.story_url_scheme = scheme
        d.scheme_of_story_url = url
        d.canonical_story_url = canonical_url
        d.title = p.title
        d.tags = [(p.subreddit.display_name or '').lower()]
        d.archived = p.archived
        d.save()
