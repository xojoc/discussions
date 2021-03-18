import datetime
import logging
import time

from celery import shared_task
from discussions.settings import APP_CELERY_TASK_MAX_TIME
from django.utils import timezone
from web import http, discussions, models
from web import celery_util
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)

# todo: handle merged stories
# story has been merged:
# e.g.: https://lobste.rs/stories/dnfxpk.json and
#       https://lobste.rs/s/7bbyke.json


class EndOfPages(Exception):
    pass

@shared_task(ignore_result=True)
def process_item(item, platform_prefix):
    story_url = (item.get('url') or '').strip()
    if not story_url:
        return

    if not item.get('comment_count'):
        return

    if item.get('score', 0) < 0:
        return

    created_at = datetime.datetime.fromisoformat(item.get('created_at'))

    scheme, url = discussions.split_scheme(story_url)
    if len(url) > 2000:
        return
    if not scheme:
        return

    canonical_url = discussions.canonical_url(url)
    if len(canonical_url) > 2000 or canonical_url == url:
        canonical_url = None

    platform_id = f"{platform_prefix}{item.get('short_id')}"

    try:
        discussion = models.Discussion.objects.get(
            pk=platform_id)

        discussion.comment_count = item.get('comment_count') or 0
        discussion.score = item.get('score') or 0
        discussion.created_at = created_at
        discussion.scheme_of_story_url = scheme
        discussion.schemeless_story_url = url
        discussion.canonical_story_url = canonical_url
        discussion.title = item.get('title')
        discussion.tags = item.get('tags')
        discussion.save()
    except models.Discussion.DoesNotExist:
        models.Discussion(
            platform_id=platform_id,
            comment_count=item.get('comment_count') or 0,
            score=item.get('score') or 0,
            created_at=created_at,
            scheme_of_story_url=scheme,
            schemeless_story_url=url,
            canonical_story_url=canonical_url,
            title=item.get('title'),
            tags=item.get('tags')).save()

def fetch_discussions(current_page, platform_prefix, base_url):
    c = http.client(with_cache=False)

    start_time = time.monotonic()

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        page_url = f"{base_url}/newest/page/{current_page}.json"

        r = c.get(page_url, timeout=7.05)

        if r.status_code == 404:
            raise EndOfPages

        page = r.json()
        if not page:
            raise EndOfPages

        for item in page:
            process_item.delay(item, platform_prefix)

        current_page += 1

        time.sleep(2.1)


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_recent_discussions():
    r = get_redis_connection("default")
    redis_prefix = 'discussions:fetch_recent_lobsters_discussions:'
    current_index = int(r.get(redis_prefix + 'current_index') or 0)
    max_index = int(r.get(redis_prefix + 'max_index') or 0)
    if not current_index or not max_index or (current_index > max_index):
        max_index = 20
        r.set(redis_prefix + 'max_index', max_index)
        current_index = 1

    try:
        current_index = fetch_discussions(current_index, 'l', 'https://lobste.rs')
    except EndOfPages:
        current_index = max_index + 1
    
    r.set(redis_prefix + 'current_index', current_index)


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_all_discussions():
    r = get_redis_connection("default")
    redis_prefix = 'discussions:fetch_all_lobsters_discussions:'
    current_index = int(r.get(redis_prefix + 'current_index') or 0)
    max_index = int(r.get(redis_prefix + 'max_index') or 0)
    if not current_index or not max_index or (current_index > max_index):
        max_index = 1000_000_000
        r.set(redis_prefix + 'max_index', max_index)
        current_index = 1

    try:
        current_index = fetch_discussions(current_index, 'l', 'https://lobste.rs')
    except EndOfPages:
        current_index = max_index + 1
    
    r.set(redis_prefix + 'current_index', current_index)

