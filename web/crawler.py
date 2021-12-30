import time
import urllib3
from . import models, discussions, http, extract, title, tags
from django.utils import timezone
import datetime
import logging
from django_redis import get_redis_connection
from celery import shared_task
from discussions.settings import APP_CELERY_TASK_MAX_TIME
from web import celery_util
from django.db.models.signals import post_save
from django.dispatch import receiver


logger = logging.getLogger(__name__)

redis_prefix = 'discussions:crawler:'
redis_queue_name = redis_prefix + 'queue'
redis_queue_medium_name = redis_prefix + 'queue_medium'
redis_queue_low_name = redis_prefix + 'queue_low'
redis_queue_zero_name = redis_prefix + 'queue_zero'
redis_host_semaphore = redis_prefix + 'semaphore:host'


@shared_task(ignore_result=True)
def add_to_queue(url, priority=0, low=False):
    r = get_redis_connection()
    if low:
        priority = 2
    if priority == 0:
        n = redis_queue_name
    elif priority == 1:
        n = redis_queue_medium_name
    elif priority == 2:
        n = redis_queue_low_name
    elif priority == 3:
        n = redis_queue_zero_name

    r.rpush(n, url)


def get_semaphore(url):
    u = urllib3.util.parse_url(url)

    if not u or not u.host:
        logger.debug("get_semaphore: parse error: {url}: {u}")
        return False

    r = get_redis_connection()

    s = r.get(redis_host_semaphore + ':' + u.host)
    if s:
        return False

    return True


def set_semaphore(url, timeout=60):
    u = urllib3.util.parse_url(url)

    if not u or not u.host:
        logger.debug("set_semaphore: parse error: {url}: {u}")
        return False

    r = get_redis_connection()

    r.set(redis_host_semaphore + ':' + u.host, 1, ex=timeout)


def fetch(url):
    one_week_ago = timezone.now() - datetime.timedelta(days=7)

    scheme, u = discussions.split_scheme(url)
    cu = discussions.canonical_url(u)

    resource = models.Resource.by_url(u)

    if not resource:
        resource = models.Resource(
            scheme=scheme,
            url=u,
            canonical_url=cu)

    if resource.last_fetch and\
       resource.last_fetch >= one_week_ago:

        logger.debug(f'recently fetched: {resource.last_fetch}: {url}')
        return True

    response = http.fetch(url, timeout=60, with_retries=False)

    if not response:
        resource.status_code = 999
    else:
        resource.status_code = response.status_code

    if resource.status_code == 200:
        html = http.parse_html(response, safe_html=True)
        resource.clean_html = str(html)
        html_structure = extract.structure(html)
        resource.title = html_structure.title

    resource.last_fetch = timezone.now()

    resource.save()

    if resource.status_code == 200:
        try:
            extract_html(resource)
        except Exception as e:
            logger.debug(f"fetch: extract html: {e}")

    return True


def process_next():
    r = get_redis_connection()
    priority = 0
    url = r.lpop(redis_queue_name)
    if not url:
        priority = 1
        url = r.lpop(redis_queue_medium_name)
        if not url:
            priority = 2
            url = r.lpop(redis_queue_low_name)
            if not url:
                priority = 3
                url = r.lpop(redis_queue_zero_name)

    if not url:
        logger.debug("process_next: no url from queue")
        return True

    url = str(url, 'utf-8')

    if url.startswith('https://streamja.com'):
        return False

    if url.startswith('https://www.reddit.com/gallery/'):
        return False

    if not get_semaphore(url):
        logger.debug(f"process_next: semaphore red: {url}")
        if priority <= 1:
            priority += 1
        add_to_queue(url, priority=priority)
        return False

    timeout = 30

    if url.startswith('https://github.com'):
        timeout = 3

    set_semaphore(url, timeout=timeout)

    try:
        fetch(url)
    except Exception as e:
        logger.warn(f"process_next: fetch fail: {e}")

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
    if created:
        if instance.story_url:
            priority = 0
            days_ago = timezone.now() - datetime.timedelta(days=14)
            one_year_ago = timezone.now() - datetime.timedelta(days=365)
            if instance.created_at:
                if instance.created_at < one_year_ago:
                    priority = 2
                elif instance.created_at < days_ago:
                    priority = 1

            add_to_queue.delay(instance.story_url, priority=priority)


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def populate_queue(comment_count=10, score=10, days=3):
    days_ago = timezone.now() - datetime.timedelta(days=days)

    discussions = models.Discussion.objects.\
        filter(created_at__gte=days_ago).\
        filter(comment_count__gte=comment_count).\
        filter(score__gte=score)

    for d in discussions:
        add_to_queue(d.story_url, priority=3)


@shared_task(ignore_result=True)
def extract_html(resource):
    if type(resource) == int:
        resource = models.Resource.objects.get(pk=resource)

    if resource.status_code != 200:
        return

    html = http.parse_html(resource.clean_html, safe_html=True)
    html_structure = extract.structure(html)
    resource.title = html_structure.title

    resource.links.clear()
    for link in html_structure.outbound_links:
        href = link.get('href')
        if not href:
            continue

        to = models.Resource.by_url(href)
        if not to:
            # xojoc: todo: call add_to_queue? so next time the relationship is created?
            continue

        anchor_title = link.get('title')
        anchor_text = link.text

        link = models.Link(from_resource=resource,
                           to_resource=to,
                           anchor_title=anchor_title,
                           anchor_text=anchor_text)
        link.save()

    resource.normalized_title = title.normalize(resource.title)
    resource.normalized_tags = tags.normalize(resource.tags)

    resource.last_processed = timezone.now()

    resource.save()
