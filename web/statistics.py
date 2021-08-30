from django.db.models import Sum, Count, Max, Min
from django.db.models.functions import Coalesce
from web import models, discussions
from celery import shared_task
from web import celery_util


def discussions_platform_statistics():
    # todo: exclude discussions with 0 comments
    stats = models.Discussion.objects.\
        values('platform').\
        annotate(discussion_count=Count('platform_id'),
                 comment_count=Sum('comment_count'),
                 date__oldest_discussion=Min('created_at'),
                 date__newest_discussion=Max('created_at')).\
        order_by('-discussion_count')

    for s in stats:
        s['platform_name'] = \
            models.Discussion.platform_name(s['platform'])
        s['platform_url'] = \
            models.Discussion.platform_url(s['platform'],
                                           preferred_external_url=discussions.PreferredExternalURL.Standard)

    return stats


def discussions_top_stories():
    stats = models.Discussion.objects.\
        annotate(canonical_url=Coalesce('canonical_story_url',
                                        'schemeless_story_url')).\
        values('canonical_url').\
        annotate(comment_count=Sum('comment_count'),
                 title=Max('title'),
                 date__last_discussion=Max('created_at'),
                 story_url=Max('schemeless_story_url')).\
        order_by('-comment_count')

    return stats[:10]


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def discussions_statistics():
    models.Statistics.\
        update_platform_statistics(list(discussions_platform_statistics()))
    models.Statistics.\
        update_top_stories_statistics(list(discussions_top_stories()))
