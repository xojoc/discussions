# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import logging
import time
from enum import Enum
from functools import total_ordering
from http import HTTPStatus
from typing import Self

import cleanurl
import urllib3
from celery import shared_task
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django_redis import get_redis_connection

from discussions.settings import APP_CELERY_TASK_MAX_TIME
from web import celery_util

from . import extract, http, models, tags, title

logger = logging.getLogger(__name__)

redis_prefix = "discussions:crawler:"


@total_ordering
class Priority(Enum):
    normal = 0
    medium = 1
    low = 2
    very_low = 3

    def __lt__(self, other):
        if self.__class__ is not other.__class__:
            return NotImplemented

        return self.value < other.value

    def lower(self: Self) -> Self:
        max_value = list(self.__class__)[-1].value
        p = min(max_value, self.value + 1)
        return Priority(p)


default_queue = redis_prefix + "queue"
queue_names = {
    Priority.normal: default_queue,
    Priority.medium: redis_prefix + "queue_medium",
    Priority.low: redis_prefix + "queue_low",
    Priority.very_low: redis_prefix + "queue_zero",
}

redis_host_semaphore = redis_prefix + "semaphore:host"


@shared_task(ignore_result=True)
def add_to_queue(
    url: str | None,
    priority: Priority = Priority.normal,
) -> None:
    if not url:
        return
    r = get_redis_connection()
    r.rpush(queue_names.get(priority), url)


def sempaphore_green(url):
    try:
        u = urllib3.util.parse_url(url)
    except ValueError:
        u = None

    if not u or not u.host:
        logger.debug(f"get_semaphore: parse error: {url}: {u}")
        return True

    r = get_redis_connection()

    s = r.get(redis_host_semaphore + ":" + u.host)
    if s:
        return False

    return True


def __set_semaphore(url: str, timeout: int = 60) -> None:
    try:
        u = urllib3.util.parse_url(url)
    except ValueError:
        u = None

    if not u or not u.host:
        logger.debug("set_semaphore: parse error: {url}: {u}")
        return

    r = get_redis_connection()

    r.set(redis_host_semaphore + ":" + u.host, 1, ex=timeout)


def fetch(url):
    one_week_ago = timezone.now() - datetime.timedelta(days=7)

    cu = cleanurl.cleanurl(url)
    if not cu:
        return None

    su = cleanurl.cleanurl(
        url,
        generic=True,
        respect_semantics=True,
        host_remap=False,
    )
    if not su:
        return None

    resource = models.Resource.by_url(url)

    if not resource:
        resource = models.Resource(
            scheme=su.scheme,
            url=su.schemeless_url,
            canonical_url=cu.schemeless_url,
        )

    if resource.last_fetch and resource.last_fetch >= one_week_ago:
        logger.debug(f"recently fetched: {resource.last_fetch}: {url}")
        return resource

    response = http.fetch(url, timeout=30, with_retries=False)

    if not response:
        resource.status_code = 999
    else:
        resource.status_code = response.status_code

    if (
        response
        and resource.status_code == HTTPStatus.OK
        and ("html" in response.headers.get("content-type", ""))
    ):
        html = http.parse_html(response, safe_html=True, clean=True)
        resource.clean_html = str(html)

    resource.last_fetch = timezone.now()

    resource.save()

    if resource.status_code == HTTPStatus.OK:
        extract_html(resource)

    return resource


def process_next() -> bool:
    r = get_redis_connection()
    priority = Priority.normal
    url = None
    for p, n in sorted(queue_names.items()):
        url = r.lpop(n)
        if url:
            priority = p
            break

    if not url:
        logger.debug("process_next: no url from queue")
        return True

    url = str(url, "utf-8")

    if url.startswith(
        (
            "https://streamja.com",
            "https://www.reddit.com/gallery/",
            "https://www.reddit.com/r/",
        ),
    ):
        return False

    if not sempaphore_green(url):
        logger.debug(f"process_next: semaphore red: {url}")
        if priority <= Priority.medium:
            priority = priority.lower()
        add_to_queue(url, priority=priority)
        return False

    timeout = 15

    if url.startswith("https://github.com"):
        timeout = 3

    if url.startswith(("https://twitter.com", "https://www.twitter.com")):
        timeout = 3

    try:
        u = urllib3.util.parse_url(url)
        if u.scheme not in {"http", "https"}:
            logger.warning("crawler: scheme not processed: %s", url)
            return False
    except ValueError:
        logger.warning("crawler:  failed to parse url: %s", url, exc_info=True)
        return False

    __set_semaphore(url, timeout=timeout)

    _ = fetch(url)

    return False


@shared_task(ignore_result=True)
def process():
    start_time = time.monotonic()

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        stop = process_next()
        if stop:
            break


@receiver(post_save, sender=models.Discussion)
def process_discussion(sender, instance, created, **kwargs):
    _ = (sender, kwargs)
    if created and instance.story_url:
        priority = Priority.normal
        days_ago = timezone.now() - datetime.timedelta(days=14)
        one_year_ago = timezone.now() - datetime.timedelta(days=365)
        if instance.created_at:
            if instance.created_at < one_year_ago:
                priority = Priority.low
            elif instance.created_at < days_ago:
                priority = Priority.medium

        add_to_queue(instance.story_url, priority=priority)


@shared_task(bind=True, ignore_result=True)
def populate_queue(self, comment_count=10, score=10, days=3):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    days_ago = timezone.now() - datetime.timedelta(days=days)

    discussions = (
        models.Discussion.objects.filter(created_at__gte=days_ago)
        .filter(comment_count__gte=comment_count)
        .filter(score__gte=score)
        .exclude(schemeless_story_url__isnull=True)
    )

    for d in discussions:
        add_to_queue(d.story_url, priority=Priority.low)


@shared_task(ignore_result=True)
def extract_html(resource):
    if isinstance(resource, int):
        resource = models.Resource.objects.get(pk=resource)

    resource.last_processed = timezone.now()

    if resource.status_code != HTTPStatus.OK:
        # TODO: python3.12 use is_success
        even = 2
        if resource.status_code // 100 != even and resource.clean_html:
            resource.clean_html = ""

        resource.save()
        return

    if not resource.clean_html:
        resource.save()
        return

    html = http.parse_html(
        resource.clean_html,
        safe_html=True,
        clean=True,
        url=resource.url,
    )
    if html:
        resource.clean_html = str(html)
    html_structure = extract.structure(html, resource.story_url)
    resource.title = html_structure.title

    resource.links.clear()
    for link in html_structure.outbound_links:
        href = link.get("href")
        if not href:
            continue

        # TODO: ignore relative and #id urls

        to = models.Resource.by_url(href)
        if not to:
            # xojoc: todo: call add_to_queue? so next time the relationship is created?
            continue

        if to.pk == resource.pk:
            continue

        anchor_title = link.get("title")
        anchor_text = link.text
        anchor_rel = link.get("rel")

        link_db = models.Link(
            from_resource=resource,
            to_resource=to,
            anchor_title=anchor_title,
            anchor_text=anchor_text,
            anchor_rel=anchor_rel,
        )
        link_db.save()

    resource.normalized_title = title.normalize(resource.title)
    resource.normalized_tags = tags.normalize(
        resource.tags,
        url=resource.story_url,
    )

    resource.save()
