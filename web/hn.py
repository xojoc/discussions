import logging
from django.utils.timezone import make_aware
import datetime
from django_redis import get_redis_connection
from web import http, models, discussions
from celery import shared_task
from discussions.settings import APP_CELERY_TASK_MAX_TIME
import time
from web import celery_util

logger = logging.getLogger(__name__)


r_skip_prefix = "discussions:hn:skip:"
r_revisit_set = "discussions:hn:revisit_set"
r_revisit_max_id = "discussions:hn:revisit_max_id"


@shared_task(ignore_result=True)
def process_item(item, revisit_max_id=None, redis=None, skip_timeout=60*60):
    if not item:
        return

    if not redis:
        redis = get_redis_connection("default")

    platform_id = f"h{item.get('id')}"

    if revisit_max_id is None or item.get('id') > revisit_max_id - 10_000:
        for kid in item.get('kids', []):
            redis.setex(r_skip_prefix + str(kid), skip_timeout, 1)

    if item.get('deleted'):
        models.Discussion.objects.filter(pk=platform_id).delete()
        return

    if item.get('type') != 'story':
        return

    if not item.get('url'):
        return

    if item.get('dead'):
        models.Discussion.objects.filter(pk=platform_id).delete()
        return

    redis.sadd(r_revisit_set, item.get('id'))

    if not item.get('time'):
        logger.info(f"HN no time: {item}")
        return

    if not item.get('descendants'):
        return

    if item.get('score') < 0:
        return

    created_at = datetime.datetime.fromtimestamp(item.get('time'))

    scheme, url = discussions.split_scheme(item.get('url'))
    if len(url) > 2000:
        return
    if not scheme:
        logger.warn(f"HN: no scheme for {platform_id}, url {item.get('url')}")
        return

    canonical_url = discussions.canonical_url(url)

    try:
        discussion = models.Discussion.objects.get(
            pk=platform_id)
        discussion.comment_count = item.get('descendants') or 0
        discussion.score = item.get('score') or 0
        discussion.created_at = make_aware(created_at)
        discussion.scheme_of_story_url = scheme
        discussion.schemeless_story_url = url
        discussion.canonical_story_url = canonical_url
        discussion.title = item.get('title')
        discussion.save()
    except models.Discussion.DoesNotExist:
        models.Discussion(
            platform_id=platform_id,
            comment_count=item.get('descendants') or 0,
            score=item.get('score') or 0,
            created_at=make_aware(created_at),
            scheme_of_story_url=scheme,
            schemeless_story_url=url,
            canonical_story_url=canonical_url,
            title=item.get('title')).save()


def fetch_item(id, revisit_max_id=None, c=None, redis=None):
    if not c:
        c = http.client(with_cache=False)
    if not redis:
        redis = get_redis_connection("default")

    if revisit_max_id:
        if (id < revisit_max_id and (not redis.sismember(r_revisit_set, id))):
            return

    if redis.exists(r_skip_prefix + str(id)):
        return

    # xojoc: if this fails, we let the whole task fail so it gets relaunched
    #        with the same parameters
    try:
        item = c.get(f"https://hacker-news.firebaseio.com/v0/item/{id}.json",
                     timeout=11.05).json()
    except Exception as e:
        time.sleep(7)
        raise(e)
    return item


def fetch_discussions(from_id, max_id):
    c = http.client(with_cache=False)
    redis = get_redis_connection("default")
    revisit_max_id = int(redis.get(r_revisit_max_id) or -1)

    start_time = time.monotonic()
    id = from_id

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        item = fetch_item(id, revisit_max_id=revisit_max_id, c=c, redis=redis)
        process_item.delay(item, revisit_max_id=revisit_max_id)
        id += 1
        if id > max_id:
            break

    redis.set(r_revisit_max_id, id)
    return id


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_all_hn_discussions():
    r = get_redis_connection("default")
    redis_prefix = 'discussions:fetch_all_hn_discussions:'
    current_index = int(r.get(redis_prefix + 'current_index') or 0)
    max_index = int(r.get(redis_prefix + 'max_index') or 0)
    if not current_index or not max_index or (current_index > max_index):
        max_index = int(http.client(with_cache=False)
                        .get("https://hacker-news.firebaseio.com/v0/maxitem.json").content) + 1
        r.set(redis_prefix + 'max_index', max_index)
        current_index = 1

    current_index = fetch_discussions(current_index, max_index)

    r.set(redis_prefix + 'current_index', current_index)


@shared_task(ignore_result=True)
def fetch_update(id, redis=None, skip_timeout=60*5):
    if redis is None:
        redis = get_redis_connection("default")
    item = fetch_item(id, redis=redis)
    if not item:
        return
    redis.setex(r_skip_prefix + str(id), skip_timeout, 1)
    if item.get("type") == "story":
        process_item.delay(item, skip_timeout=skip_timeout)
    if item.get("type") == "comment":
        if item.get("parent"):
            fetch_update(item.get("parent"),
                         redis=redis,
                         skip_timeout=skip_timeout)


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_updates():
    c = http.client(with_cache=False)
    updates = c.get("https://hacker-news.firebaseio.com/v0/updates.json",
                    timeout=7.05).json()

    for id in updates.get('items'):
        fetch_update(id)
