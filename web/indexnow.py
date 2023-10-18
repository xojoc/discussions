# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
import os

import requests
from celery import shared_task
from django.db.models.signals import post_save
from django.dispatch import receiver

from . import models, util

logger = logging.getLogger(__name__)


@receiver(post_save, sender=models.Discussion)
def process_discussion(sender, instance, created, **kwargs):
    # TODO: disabled for now

    return
    # if not instance.story_url:

    # if not created:

    # if instance.comment_count < 100:


@shared_task(ignore_result=True)
def indexnow(url):
    key = os.getenv("INDEX_NOW_API_KEY", "")
    if not key:
        return
    if util.is_dev():
        print(f"IndexNow: {url}")
        return

    r = requests.get(
        "https://bing.com/indexnow",
        params={"url": url, "key": key},
    )
    if not r.ok:
        logger.error(f"IndeNow failed: {url} {r.status_code} {r.reason}")
