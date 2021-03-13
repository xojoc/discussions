from web import hn, celery_util
from . import http
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_all_hn_discussions():
    print("test")
    logger.info("test")
    celery_util.split_task('discussions:fetch_all_hn_discussions:',
                           lambda _: 1,
                           lambda: int(http.client(with_cache=False)
                                       .get("https://hacker-news.firebaseio.com/v0/maxitem.json").content) + 1,
                           10_000,
                           lambda f, t: hn.fetch_discussions(f, t))
