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
redis_host_semaphore = redis_prefix + 'semaphore:host'


@shared_task(ignore_result=True)
def add_to_queue(url):
    r = get_redis_connection()
    r.rpush(redis_queue_name, url)


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

    response = http.fetch(url, timeout=60)

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
        extract_html.delay(resource.id)

    return True


def process_next():
    r = get_redis_connection()
    url = r.lpop(redis_queue_name)

    if not url:
        logger.debug("process_next: no url from queue")
        return True

    url = str(url, 'utf-8')

    if not get_semaphore(url):
        logger.debug(f"process_next: semaphore red: {url}")
        add_to_queue(url)
        return False

    fetched = False

    try:
        fetched = fetch(url)
    except Exception as e:
        logger.warn(f"process_next: fetch fail: {e}")

    if fetched:
        set_semaphore(url)

    return False


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def process():
    start_time = time.monotonic()

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        stop = process_next()
        if stop:
            break


@receiver(post_save, sender=models.Discussion)
def process_discussion(sender, instance, created, **kwargs):
    if created:
        add_to_queue.delay(instance.story_url)


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def populate_queue():
    three_days_ago = timezone.now() - datetime.timedelta(days=3)

    discussions = models.Discussion.objects.\
        filter(created_at__gte=three_days_ago).\
        filter(comment_count__gte=10).\
        filter(score__gte=10)

    for d in discussions:
        add_to_queue(d.story_url)


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
