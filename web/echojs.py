import datetime
import logging
import time

import cleanurl
from celery import shared_task
from django.core.cache import cache
from django.utils.timezone import make_aware

from web.platform import Platform

from . import celery_util, http, models, worker

logger = logging.getLogger(__name__)


def __process_item(item, platform):
    platform_id = f"{platform}{item.get('id')}"

    if item.get("ctime"):
        created_at = datetime.datetime.fromtimestamp(int(item.get("ctime")))
        created_at = make_aware(created_at)
    else:
        created_at = None

    scheme, url = None, None
    if item.get("url") and (
        item.get("url").startswith("http://")
        or item.get("url").startswith("https://")
    ):
        u = cleanurl.cleanurl(
            item.get("url"),
            generic=True,
            respect_semantics=True,
            host_remap=False,
        )
        if u:
            scheme = u.scheme
            url = u.schemeless_url

    score = int(item.get("up", 0)) - int(item.get("down", 0))

    models.Discussion.objects.update_or_create(
        pk=platform_id,
        defaults={
            "comment_count": int(item.get("comments", 0)),
            "score": score,
            "created_at": created_at,
            "scheme_of_story_url": scheme,
            "schemeless_story_url": url,
            "title": item.get("title"),
        },
    )


def __worker_fetch(task, platform):
    client = http.client(with_cache=False)
    base_url = Platform(platform).value
    cache_current_index_key = f"discussions:echojs:{platform}:current_index"

    current_index = cache.get(cache_current_index_key) or 0
    current_index = int(current_index)

    while True:
        if worker.graceful_exit(task):
            logger.info(f"echojs {platform} fetch: graceful exit")
            break

        indexes = [current_index]

        count = 20

        if current_index > 0 and current_index % (10 * count) == 0:
            indexes.append(0)

        for index in indexes:
            logger.debug(f"echojs {platform}: {index}")
            page_url = f"{base_url}/api/getnews/latest/{index}/{count}"
            r = client.get(page_url, timeout=11.05)
            if not r.ok:
                logger.warning(f"echojs not ok: {r.reason}: {current_index}")
                current_index = 0
                break

            j = r.json()

            if not j.get("news"):
                current_index = 0
                break

            for item in j.get("news"):
                __process_item(item, platform)

            time.sleep(10)

        current_index += count

        cache.set(cache_current_index_key, current_index, timeout=None)


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_fetch_echojs(self):
    __worker_fetch(self, "e")
