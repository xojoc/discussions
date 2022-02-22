import logging

from celery import shared_task
from celery.utils.log import get_task_logger

from web import archiveis  # noqa F401
from web import crawler  # noqa F401
from web import db  # noqa F401
from web import discussions  # noqa F401
from web import echojs  # noqa F401
from web import email_util  # noqa F401
from web import hn  # noqa F401
from web import indexnow  # noqa F401
from web import lobsters  # noqa F401
from web import ltu  # noqa F401
from web import mastodon  # noqa F401
from web import reddit  # noqa F401
from web import statistics  # noqa F401
from web import twitter  # noqa F401
from web import weekly  # noqa F401
from web import worker  # noqa F401

from . import celery_util

logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)


@shared_task(ignore_result=True, bind=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def test_task(self):
    logger.info("started test_task")
    logger.error("this is an error!")

    print("test stdout")

    task_logger.info("task logger info")
    task_logger.error("task logger error")

    f = open("/tmp/test_task", "a")
    f.write("hey there\n")
    f.close()

    return

    # breakpoint()

    import time

    time.sleep(30)

    raise Exception("test lock")

    # import time

    # c = 0
    # while True:
    #     logger.info("loop")
    #     time.sleep(1)
    #     c += 1
    #     if c % 3 == 0:
    #         if worker.graceful_exit(self):
    #             break

    # logger.info("graceful exit")
