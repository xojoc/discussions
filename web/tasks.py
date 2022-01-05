import logging
from web import hn, lobsters, reddit, statistics  # noqa F401
from web import discussions, twitter, mastodon, archiveis  # noqa F401
from web import ltu, db, crawler, worker  # noqa F401
from web import echojs  # noqa F401
from celery import shared_task
from . import celery_util

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True, bind=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def test_task(self):
    logger.info("started test_task")

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
