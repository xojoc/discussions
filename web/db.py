import time
import logging
from web import models, celery_util, crawler, discussions
from celery import shared_task
from django.utils import timezone
import datetime


logger = logging.getLogger(__name__)


def timing_iterate_all(chunk_size=10_000):
    start_time = time.monotonic()
    stories = models.Discussion.objects.all().order_by()
    for _ in stories.iterator(chunk_size=chunk_size):
        pass

    logger.info(f"db iterate all: {time.monotonic() - start_time}")


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def update_db():
    start_time = time.monotonic()
    count_dirty = 0
    count_dirty_resource = 0
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)
    stories = models.Discussion.\
        objects.filter(entry_updated_at__lte=seven_days_ago).order_by()

    logger.info(f"db update: count {stories.count()}")

    dirty_stories = []

    def __update(dirty_stories):
        updated_count = models.Discussion.objects.bulk_update(dirty_stories,
                                                              ['canonical_story_url',
                                                               'normalized_tags',
                                                               'normalized_title'])
        logger.info(f"db update: updated: {updated_count}")
        dirty_stories[:] = []

    for story in stories.iterator(chunk_size=10_000):
        dirty = False

        canonical_story_url = story.canonical_story_url
        normalized_title = story.normalized_title
        normalized_tags = story.normalized_tags

        if story.schemeless_story_url:
            story.canonical_story_url = discussions.canonical_url(story.schemeless_story_url)

        story._pre_save()

        if story.canonical_story_url != canonical_story_url or\
           story.normalized_title != normalized_title or \
           story.normalized_tags != normalized_tags:

            dirty = True

        if dirty:
            count_dirty += 1
            dirty_stories.append(story)

        if len(dirty_stories) >= 1000:
            __update(dirty_stories)

        resource = models.Resource.by_url(story.schemeless_story_url)
        if resource:
            if resource.last_fetch and\
               resource.status_code == 200 and\
               (not resource.last_processed or resource.last_processed < resource.last_fetch):

                crawler.extract_html.delay(resource.id)
                count_dirty_resource += 1

    if len(dirty_stories) > 0:
        __update(dirty_stories)

    logger.info(f"db update: total dirty: {count_dirty}")
    logger.info(f"db update: total resource dirty: {count_dirty_resource}")
    logger.info(f"db update: {time.monotonic() - start_time}")
