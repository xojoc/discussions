import datetime
import logging
import time
from celery import shared_task
from . import http, discussions, models
from . import celery_util, worker
from django.core.cache import cache

logger = logging.getLogger(__name__)

# todo: handle merged stories
# story has been merged:
# e.g.: https://lobste.rs/stories/dnfxpk.json and
#       https://lobste.rs/s/7bbyke.json


def process_item(item, platform):
    platform_id = f"{platform}{item.get('short_id')}"

    created_at = datetime.datetime.fromisoformat(item.get('created_at'))

    scheme, url, canonical_url = None, None, None
    if item.get('url'):
        scheme, url = discussions.split_scheme(item.get('url').strip())
        canonical_url = discussions.canonical_url(url)

    models.Discussion.objects.update_or_create(
        pk=platform_id,
        defaults={'comment_count': item.get('comment_count') or 0,
                  'score': item.get('score') or 0,
                  'created_at': created_at,
                  'scheme_of_story_url': scheme,
                  'schemeless_story_url': url,
                  'canonical_story_url': canonical_url,
                  'title': item.get('title'),
                  'tags': item.get('tags')})


def __worker_fetch(task, platform):
    client = http.client(with_cache=False)
    base_url = models.Discussion.platform_url(platform)
    cache_current_page_key = f'discussions:lobsters:{platform}:current_page'

    current_page = cache.get(cache_current_page_key) or 1
    current_page = int(current_page)

    while True:
        pages = [current_page]

        if current_page % 10 == 0:
            pages.extend([1, 2])

        for page in pages:
            logger.debug(f"lobsters {platform}: {page}")
            page_url = f"{base_url}/newest/page/{page}.json"
            r = client.get(page_url, timeout=11.05)
            if r.status_code == 404:
                current_page = 0
                break

            for item in r.json():
                process_item(item, platform)

            time.sleep(10)

        current_page += 1

        cache.set(cache_current_page_key, current_page, timeout=None)

        if worker.graceful_exit(task):
            logger.info(f"lobsters {platform} fetch: graceful exit")
            break


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_fetch_lobsters(self):
    __worker_fetch(self, 'l')


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_fetch_barnacles(self):
    __worker_fetch(self, 'b')
