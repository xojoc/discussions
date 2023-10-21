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

# import all the modules containing Celery tasks
_ = archiveis
_ = crawler
_ = db
_ = discussions
_ = echojs
_ = email_util
_ = hn
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
    # Go to deepest stack frame (usually the one with our own code) and
    #  get the local variables
    tb = kwargs.get("traceback")
    while tb and tb.tb_next:
        tb = tb.tb_next
    tb_locals = tb.tb_frame.f_locals if tb else {}

    email_util.send_admins(
        f"Celery: task failure: {kwargs['task_id']}",
        f"""

        {pprint.pformat(kwargs, indent=4, underscore_numbers=True)}

        {kwargs['einfo']}


        {pprint.pformat(tb_locals, indent=4, underscore_numbers=True)}

        """,
    )


@task_internal_error.connect()
def celery_internal_error_email(
    sender: celery.Task,
    **kwargs: Any,
) -> None:
    _ = sender
    tb = kwargs.get("traceback")
    while tb and tb.tb_next:
        tb = tb.tb_next

    tb_locals = tb.tb_frame.f_locals if tb else {}
    email_util.send_admins(
        f"Celery: internal error: {kwargs['task_id']}",
        f"""

        {pprint.pformat(kwargs, indent=4, underscore_numbers=True)}

        {kwargs['einfo']}

        {pprint.pformat(tb_locals, indent=4, underscore_numbers=True)}

        """,
    )


@shared_task(ignore_result=True)
def celery_explicit_error():
    """Cause an error to test the `task_failure` signal"""
    local_error = "I'am local"
    _ = local_error
    msg = "testing the `task_failure` signal"
    raise ValueError(msg)
