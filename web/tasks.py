from . import http
from celery import shared_task
import logging
from web import hn, lobsters, reddit

logger = logging.getLogger(__name__)
