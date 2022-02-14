import logging
from enum import Enum

from web import models

from celery import shared_task

logger = logging.getLogger(__name__)


class PreferredExternalURL(Enum):
    Standard = 1
    Mobile = 2
    Old = 3


@shared_task(ignore_result=True)
def delete_useless_discussions():
    models.Discussion.delete_useless_discussions()
