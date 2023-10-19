# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
import pprint
from typing import Any

import celery
from celery import shared_task
from celery.signals import task_failure, task_internal_error
from celery.utils.log import get_task_logger

from web import (
    archiveis,
    crawler,
    db,
    discussions,
    echojs,
    email_util,
    hn,
    indexnow,
    lobsters,
    ltu,
    mastodon,
    mention,
    reddit,
    statistics,
    stripe_util,
    twitter,
    weekly,
    worker,
)

from . import celery_util

logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)


_ = archiveis
_ = crawler
_ = db
_ = discussions
_ = echojs
_ = email_util
_ = hn
_ = indexnow
_ = lobsters
_ = ltu
_ = mastodon
_ = mention
_ = reddit
_ = statistics
_ = stripe_util
_ = twitter
_ = weekly
_ = worker


@shared_task(ignore_result=True, bind=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def test_task(self):
    _ = self
    logger.info("started test_task")
    logger.error("this is an error!")

    task_logger.info("task logger info")
    task_logger.error("task logger error")


@task_failure.connect()
def celery_task_failure_email(
    sender: celery.Task,
    **kwargs: Any,
) -> None:
    _ = sender
    email_util.send_admins(
        f"Celery: task failure: {kwargs['task_id']}",
        f"""

        {pprint.pformat(kwargs, indent=4, underscore_numbers=True)}

        {kwargs['einfo']}

        """,
    )


@task_internal_error.connect()
def celery_internal_error_email(sender: celery.Task, **kwargs: Any):
    _ = sender
    email_util.send_admins(
        f"Celery: internal error: {kwargs['task_id']}",
        f"""

        {pprint.pformat(kwargs, indent=4, underscore_numbers=True)}

        {kwargs['einfo']}

        """,
    )


@shared_task(ignore_result=True)
def celery_explicit_error():
    """Cause an error to test the `task_failure` signal"""
    raise ValueError("testing the `task_failur` signal")
