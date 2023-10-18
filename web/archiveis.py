# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import archiveis
from celery import shared_task


@shared_task(ignore_result=True)
def capture(url):
    return archiveis.capture(url)


def archive_url(url):
    return f"https://archive.md/newest/{url}"
