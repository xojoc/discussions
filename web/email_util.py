import email
import imaplib
import logging
import re
from email.message import Message

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail as django_send_mail

from . import celery_util, http, util, weekly

logger = logging.getLogger(__name__)


@shared_task(
    ignore_result=True,
    rate_limit=3,
    autoretry_for=(Exception,),
    retry_backoff=2 * 60,
    retry_backoff_max=60 * 60,
    retry_kwargs={"max_retries": 5},
)
def send_task(subject: str, body: str, from_email: str, to_emails: list[str]) -> None:
    if util.is_dev():
        subject = "[DEV] " + subject
    django_send_mail(subject, body, from_email, to_emails)


def send(subject: str, body: str, from_email: str, to_emails: str | list[str]) -> None:
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    send_task.delay(subject, body, from_email, to_emails)


def send_admins(subject, body):
    send(
        f"[discu.eu]: {subject}",
        body,
        settings.SERVER_EMAIL,
        settings.ADMINS[0][1],
    )


def imap_client():
    m = imaplib.IMAP4_SSL(settings.EMAIL_IMAP_HOST)
    m.login(settings.EMAIL_IMAP_USER, settings.EMAIL_IMAP_PASSWORD)
    status, messages = m.select(mailbox=settings.EMAIL_IMAP_MAILBOX)
    return m, status, messages


email_imap_handlers = [weekly.imap_handler]


def __get_imap_field(message: Message, key: str) -> str:
    return message.get(key, "")


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_fetch_and_dispatch_email(self):
    _ = self
    m, _, messages = imap_client()

    logger.debug(f"Email messages {messages}")

    for id in range(1, int(messages[0]) + 1):
        logger.debug(f"Email id {id}")
        _, data = m.fetch(str(id), "(RFC822)")
        message = email.message_from_bytes(
            data[0][1],
            policy=email.policy.default.clone(utf8=True),
        )
        if not message:
            logger.debug("Cannot decode message")
            continue
        body = None
        message_id = __get_imap_field(message, "Message-Id")
        from_email = __get_imap_field(message, "From")
        try:
            address = re.search(r"<([ @a-zA-Z\.0-9_\-\+]+)>", from_email)[1]
            from_email = address
        except Exception:
            pass
        from_email = from_email.strip()

        to_email = __get_imap_field(message, "To")
        try:
            address = re.search(r"<([ @a-zA-Z\.0-9_\-\+]+)>", to_email)[1]
            to_email = address
        except Exception:
            pass
        to_email = to_email.strip()

        subject = __get_imap_field(message, "Subject")

        if settings.EMAIL_TO_PREFIX and (
            not to_email or not to_email.startswith(settings.EMAIL_TO_PREFIX)
        ):
            logger.debug(f"Email skipping {to_email} {subject}")
            continue

        if message.get_body().get_content_type() == "text/plain":
            body = message.get_body().get_content()
        if message.get_body().get_content_type() == "text/html":
            body = http.parse_html(message.get_body().get_content()).get_text(
                " ",
                strip=True,
            )

        if not body or not from_email or not to_email or not subject:
            logger.debug("Email data missing... skipping")
            continue

        handled = False
        for handler in email_imap_handlers:
            handled = handler(
                message,
                message_id,
                from_email,
                to_email,
                subject,
                body,
            )
            if handled:
                break

        if handled:
            m.store(str(id), "+FLAGS", "(\\Deleted)")

    m.close()
    m.logout()
