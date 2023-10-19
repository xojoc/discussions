# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail as django_send_mail

from . import util

logger = logging.getLogger(__name__)


@shared_task(
    ignore_result=True,
    rate_limit="3/s",
    autoretry_for=(Exception,),
    retry_backoff=2 * 60,
    retry_backoff_max=60 * 60,
    retry_kwargs={"max_retries": 5},
)
def send_task(
    subject: str,
    body: str,
    from_email: str,
    to_emails: list[str],
) -> None:
    if util.is_dev():
        subject = "[DEV] " + subject
    _ = django_send_mail(subject, body, from_email, to_emails)


def send(
    subject: str,
    body: str,
    from_email: str,
    to_emails: str | list[str],
    *,
    no_task: bool = False,
) -> None:
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    if no_task:
        send_task(subject, body, from_email, to_emails)
    else:
        _ = send_task.delay(subject, body, from_email, to_emails)


def send_admins(subject: str, body: str, *, no_task: bool = False) -> None:
    send(
        f"[discu.eu]: {subject}",
        body,
        settings.SERVER_EMAIL,
        settings.ADMINS[0][1],
        no_task=no_task,
    )
