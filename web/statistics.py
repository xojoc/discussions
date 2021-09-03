from django.db.models import Sum, Count, Max, Min, Value
from django.db.models.functions import Coalesce, Left, StrIndex, NullIf, Length
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


def discussions_top_domains():
    stats = models.Discussion.objects.\
        annotate(canonical_url=Coalesce('canonical_story_url',
                                        'schemeless_story_url')).\
        annotate(domain=Left('canonical_url',
                             Coalesce(NullIf(StrIndex('canonical_url', Value('/')), 0) - 1, Length('canonical_url')))).\
        values('domain').\
        annotate(comment_count=Sum('comment_count'),
                 discussion_count=Count('platform_id')).\
        order_by('-discussion_count')

    return stats[:10]


@shared_task(ignore_result=True)
@celery_util.singleton(timeout=240, blocking_timeout=120)
def discussions_statistics():
    models.Statistics.\
        update_platform_statistics(list(discussions_platform_statistics()))
    models.Statistics.\
        update_top_stories_statistics(list(discussions_top_stories()))
    models.Statistics.\
        update_top_domains_statistics(list(discussions_top_domains()))
