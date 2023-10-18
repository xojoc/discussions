# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
from enum import Enum

from celery import shared_task

from web import models

logger = logging.getLogger(__name__)


class PreferredExternalURL(Enum):
    Standard = 1
    Mobile = 2
    Old = 3


@shared_task(ignore_result=True)
def delete_useless_discussions():
    models.Discussion.delete_useless_discussions()
