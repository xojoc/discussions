# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import logging
import time
from typing import Any

import celery
import cleanurl
import django
import django.db
import requests
from celery import shared_task
from django.core.cache import cache

from web.platform import Platform

from . import celery_util, http, models, worker

logger = logging.getLogger(__name__)

# TODO: handle merged stories
# story has been merged:
# e.g.: https://lobste.rs/stories/dnfxpk.json and
#       https://lobste.rs/s/7bbyke.json


def process_item(item: dict[str, Any], platform: Platform) -> None:
    platform_id = f"{platform.value}{item.get('short_id')}"

    created_at = datetime.datetime.fromisoformat(item.get("created_at"))

    scheme, url = None, None
    if item.get("url"):
        u = cleanurl.cleanurl(
            item.get("url"),
            generic=True,
            respect_semantics=True,
            host_remap=False,
        )
        if u:
            scheme = u.scheme
            url = u.schemeless_url

    try:
        discussion = models.Discussion.objects.get(pk=platform_id)
        discussion.comment_count = item.get("comment_count") or 0
        discussion.score = item.get("score") or 0
        discussion.created_at = created_at
        discussion.scheme_of_story_url = scheme
        discussion.schemeless_story_url = url
        discussion.title = item.get("title")
        discussion.tags = item.get("tags")
        discussion.save()
    except models.Discussion.DoesNotExist:
        try:  # noqa: SIM105
            models.Discussion(
                platform_id=platform_id,
                comment_count=item.get("comment_count") or 0,
                score=item.get("score") or 0,
                created_at=created_at,
                scheme_of_story_url=scheme,
                schemeless_story_url=url,
                title=item.get("title"),
                tags=item.get("tags"),
            ).save()
        except Exception:  # noqa: S110, BLE001
            # TODO: remove
            pass


def __worker_fetch(task: celery.Task, platform: Platform) -> None:
    client = http.client(with_cache=False)
    base_url = platform.url
    cache_current_page_key = f"discussions:lobsters:{platform}:current_page"

    current_page = cache.get(cache_current_page_key) or 1
    current_page = int(current_page)

    while True:
        if worker.graceful_exit(task):
            logger.info(f"lobsters {platform} fetch: graceful exit")
            break

        pages = [current_page]

        if current_page % 10 == 0:
            pages.extend([1, 2])

        for page in pages:
            logger.debug(f"lobsters {platform}: {page}")
            page_url = f"{base_url}/newest/page/{page}.json"
            try:
                r = client.get(page_url, timeout=31.05)
            except requests.exceptions.RequestException:
                logger.warning(
                    "lobsters worker fetch: %s: error get",
                    platform.label,
                    exc_info=True,
                )
                time.sleep(30)
                # re-fetch this page
                current_page -= 1
                break
            if not r or r.status_code == 404:
                current_page = 0
                break

            for item in r.json():
                process_item(item, platform)

            django.db.connections.close_all()
            time.sleep(2 * 60)

        current_page += 1

        cache.set(cache_current_page_key, current_page, timeout=None)


@shared_task(bind=True, ignore_result=True)
def worker_fetch_lobsters(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    __worker_fetch(self, Platform.LOBSTERS)


@shared_task(bind=True, ignore_result=True)
def worker_fetch_barnacles(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    __worker_fetch(self, Platform.BARNACLES)


@shared_task(bind=True, ignore_result=True)
def worker_fetch_tilde_news(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    __worker_fetch(self, Platform.TILDE_NEWS)


@shared_task(bind=True, ignore_result=True)
def worker_fetch_standard(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    __worker_fetch(self, Platform.STANDARD)
