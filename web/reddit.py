import datetime
import io
import json
import logging
import os
import re
import shutil
import time

import praw
import prawcore
import zstandard
from celery import shared_task
from django.conf import settings
from django.db import IntegrityError
from django.utils.timezone import make_aware
from django_redis import get_redis_connection
from discussions.settings import APP_CELERY_TASK_MAX_TIME
from django.core.cache import cache

from . import celery_util, worker
from . import http, models, discussions
import pickle

logger = logging.getLogger(__name__)

# filled in apps.WebConfig.ready
subreddit_blacklist = set()
subreddit_whitelist = set()


def url_blacklisted(url):
    if url.startswith('i.imgur.com') or \
            url.startswith('imgur.com') or \
            url.startswith('gfycat.com'):
        return True

    return False


def __process_archive_line(line):
    p = json.loads(line)
    if p.get('subreddit') not in subreddit_whitelist:
        # logger.debug(f"subreddit skipped {p.get('subreddit')}")
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
    if (p.get('score') or 0) < 1:
        return
    if (p.get('num_comments') or 0) <= 2:
        return

    platform_id = 'r' + p.get('id')

    scheme, url, canonical_url = None, None, None

    if p.get('url'):
        scheme, url = discussions.split_scheme(p.get('url'))
        if scheme:
            canonical_url = discussions.canonical_url(url)
            if url_blacklisted(canonical_url or url):
                return
        else:
            logging.warning(
                f"Reddit archive: no scheme for {platform_id}, url {p.get('url')}")
            return

    created_at = None
    if p.get('created_utc'):
        created_at = datetime.datetime.fromtimestamp(int(p.get('created_utc')))
        created_at = make_aware(created_at)

    subreddit = p.get('subreddit') or ''
    if not subreddit:
        logger.warn(f"Reddi archive: no subreddit {platform_id}")
        return

    try:
        models.Discussion.objects.create(platform_id=platform_id,
                                         comment_count=p.get('num_comments') or 0,
                                         score=p.get('score') or 0,
                                         created_at=created_at,
                                         scheme_of_story_url=scheme,
                                         schemeless_story_url=url,
                                         canonical_story_url=canonical_url,
                                         title=p.get('title'),
                                         tags=[subreddit.lower()])
    except IntegrityError:
        pass
    except Exception as e:
        logger.warning(f"Reddit archive: {e}")
        return


def __get_reddit_archive_links(client, starting_from=None):
    url_prefix = 'https://files.pushshift.io/reddit/submissions/'
    digests = client.get(url_prefix + 'sha256sums.txt')
    available_files = []
    for line in digests.content.decode().split("\n"):
        fields = line.split()
        if len(fields) >= 2:
            available_files.append(fields[1])

    chosen_files = []

    for file in available_files:
        match = re.findall(r"RS.*(\d\d\d\d)-(\d\d)\.zst", file)[0]
        year_month = match[0] + "-" + match[1]

        if starting_from and year_month < starting_from:
            continue

        chosen_files.append(url_prefix + file)

    return chosen_files


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_fetch_reddit_archive(self):
    client = http.client(with_cache=False)
    cache_prefix = 'fetch_reddit_archive'
    cache_timeout = 60 * 60 * 24 * 90

    for file in __get_reddit_archive_links(client):
        if cache.get(f"{cache_prefix}:processed:{file}"):
            continue

        if worker.graceful_exit(self):
            logger.info("reddit archive: graceful exit")
            break

        logger.info(f"reddit archive: processing {file}")

        file_name = '/tmp/discussions_reddit_archive_compressed'

        if not os.path.isfile(file_name):
            cache.delete(f"{cache_prefix}:downloaded:{file}")

        if not cache.get(f"{cache_prefix}:downloaded:{file}"):
            with client.get(file, stream=True) as res:
                logger.info(f"reddit archive: start download {file}")
                f = open(file_name, 'wb')
                shutil.copyfileobj(res.raw, f)
                f.close()
                logger.info(f"reddit archive: end download {file}")
                cache.set(f"{cache_prefix}:downloaded:{file}",
                          1,
                          timeout=cache_timeout)

        f = open(file_name, 'rb')

        stream = zstandard.ZstdDecompressor(max_window_size=2**31).\
            stream_reader(f, read_across_frames=True)

        text = io.TextIOWrapper(stream)

        graceful_exit = False

        c = 0
        for line in text:
            if c % 1_000_000 == 0:
                logger.info(f"reddit archive: File {file}, line {c}")
                if worker.graceful_exit(self):
                    logger.info("reddit archive: graceful exit")
                    graceful_exit = True
                    break

            c += 1
            try:
                __process_archive_line(line)
            except Exception as e:
                logger.info(f"reddit archive: line failed: {e}\n\n{line}")

        stream.close()
        f.close()
        os.remove(file_name)

        if not graceful_exit:
            cache.set(f"{cache_prefix}:processed:{file}",
                      1,
                      timeout=cache_timeout)

        time.sleep(5)


class EndOfSubreddits(Exception):
    pass


def client(with_cache=False, with_retries=True):
    c = praw.Reddit(client_id=settings.REDDIT_CLIENT_ID,
                    client_secret=settings.REDDIT_CLIENT_SECRET,
                    user_agent=settings.USERAGENT,
                    requestor_kwargs={
                        'session':
                        http.client(with_cache=with_cache,
                                    with_retries=with_retries)
                    })
    return c


def get_subreddit(subreddit,
                  listing='new',
                  listing_argument='',
                  redis_client=None,
                  reddit_client=None):

    if not redis_client:
        redis_client = get_redis_connection("default")
    subreddit = subreddit.lower()
    redis_key = f'discussions:subreddit_cache:{listing}:{listing_argument}:{subreddit}'

    stories = set()
    for story in redis_client.smembers(redis_key):
        stories.add(pickle.loads(story, encoding='UTF-8'))
    if stories:
        return stories

    if not reddit_client:
        reddit_client = client()
    list = None
    if listing == 'new':
        list = reddit_client.subreddit(subreddit).new(limit=50)
    if listing == 'top':
        list = reddit_client.subreddit(subreddit).top(listing_argument,
                                                      limit=30)

    for story in list:
        _ = story.title  # force load
        redis_client.sadd(redis_key, pickle.dumps(story))
        stories.add(story)

    redis_client.expire(redis_key, 60 * 7)

    return stories


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

        try:
            stories = get_subreddit(name,
                                    redis_client=redis,
                                    reddit_client=reddit)
        except Exception as e:
            logger.warning(f"reddit: subreddit {name}: {e}")
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
                    redis.set(temporary_skip_key_prefix + p.id,
                              1,
                              ex=cache_timeout)
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
                    discussion = models.Discussion.objects.get(pk=platform_id)
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
                    models.Discussion(platform_id=platform_id,
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
                redis.set(temporary_skip_key_prefix + p.id, 1, ex=60 * 15)

        except (prawcore.exceptions.Forbidden, prawcore.exceptions.NotFound,
                prawcore.exceptions.PrawcoreException) as e:
            logger.warning(f"reddit: subreddit {name}: {e}")
            continue

        if not subreddit_max_created_at or max_created_at > float(
                subreddit_max_created_at):
            redis.set(max_created_at_key + name,
                      max_created_at,
                      ex=60 * 60 * 24 * 180)
        else:
            # No new story. Skip this subreddit for a while
            redis.set(skip_sub_key_prefix + name, 1, ex=60 * 60)

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


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_update_all_discussions(self):
    reddit = client()
    cache_current_index_key = 'discussions:reddit_update:current_index'
    current_index = cache.get(cache_current_index_key) or 0

    logger.debug(f"reddit update all: current index: {current_index}")

    q = (models.Discussion.objects.filter(platform='r').filter(
        archived=False).order_by('pk'))

    logger.debug(f"reddit update all: count {q.count()}")

    while True:
        if worker.graceful_exit(self):
            logger.info("reddit update all: graceful exit")
            break

        ps = []
        ds = []
        query_has_results = False

        step = 100

        for d in q[current_index:current_index+step].iterator():
            query_has_results = True

            if d.subreddit.lower() in subreddit_blacklist:
                d.delete()
                continue
            if url_blacklisted(d.canonical_story_url or d.schemeless_story_url):
                d.delete()
                continue
            if d.subreddit not in subreddit_whitelist:
                d.delete()
                continue

            ps.append(f't3_{d.id}')
            ds.append(d)

        if not query_has_results:
            logger.debug(f"reddit update all: query with no results: {current_index}")
            current_index = 0
            cache.set(cache_current_index_key, current_index, timeout=None)
            continue

        for i, p in enumerate(reddit.info(ps)):
            d = ds[i]

            if p.over_18:
                d.delete()
                continue

            d.comment_count = p.num_comments or 0
            d.score = p.score or 0
            d.title = p.title
            # d.tags = [(p.subreddit.display_name or '').lower()]
            d.archived = p.archived
            d.save()

        current_index += step

        cache.set(cache_current_index_key, current_index, timeout=None)

        time.sleep(10)
