from __future__ import annotations  # for union type
from django.core.mail import send_mail as django_send_mail
from celery import shared_task
from typing import List
from web import util


@shared_task(ignore_result=True)
def send_task(subject: str, body: str, from_email: str, to_emails: List[str]):
    if util.is_dev():
        to_emails = ["hi@xojoc.pw"]
    django_send_mail(subject, body, from_email, to_emails)


def send(subject: str, body: str, from_email: str, to_emails: str | List[str]):
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    send_task.delay(subject, body, from_email, to_emails)
