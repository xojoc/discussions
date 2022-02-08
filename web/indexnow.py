from django.db.models.signals import post_save
from django.dispatch import receiver
from celery import shared_task
import requests
import os
import logging
from . import models, util


logger = logging.getLogger(__name__)


@receiver(post_save, sender=models.Discussion)
def process_discussion(sender, instance, created, **kwargs):
    if not instance.story_url:
        return

    if not created:
        return

    indexnow.delay(util.discussions_canonical_url(instance.story_url))


@shared_task(ignore_result=True)
def indexnow(url):
    key = os.getenv('INDEX_NOW_API_KEY', '')
    if not key:
        return
    if util.is_dev():
        print(f"IndexNow: {url}")
        return

    r = requests.get('https://bing.com/indexnow',
                     params={'url': url, 'key': key})
    if not r.ok:
        logger.error(f'IndeNow failed: {url} {r.status_code} {r.reason}')
