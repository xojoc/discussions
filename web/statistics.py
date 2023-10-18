# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
from celery import shared_task
from django.db.models import Count, Max, Min, Sum, Value
from django.db.models.functions import (
    Coalesce,
    Concat,
    Left,
    Length,
    NullIf,
    StrIndex,
)

from web import celery_util, discussions, models
from web.platform import Platform


def discussions_platform_statistics():
    stats = (
        models.Discussion.objects.exclude(canonical_story_url__isnull=True)
        .values("_platform")
        .annotate(
            discussion_count=Count("platform_id"),
            comment_count=Sum("comment_count"),
            date__oldest_discussion=Min("created_at"),
            date__newest_discussion=Max("created_at"),
        )
        .order_by("-discussion_count")
    )

    for s in stats:
        s["platform"] = Platform(s["_platform"])

    return stats


def discussions_top_stories():
    stats = (
        models.Discussion.objects.exclude(canonical_story_url__isnull=True)
        .exclude(canonical_story_url__startswith="reddit.com/")
        .values("canonical_story_url")
        .annotate(
            comment_count=Sum("comment_count"),
            title=Max("title"),
            date__last_discussion=Max("created_at"),
            story_url=Concat(
                Max("scheme_of_story_url"),
                Value("://"),
                Max("schemeless_story_url"),
            ),
        )
        .order_by("-comment_count")
    )

    return stats[:17]


def discussions_top_domains():
    stats = (
        models.Discussion.objects.exclude(canonical_story_url__isnull=True)
        .filter(comment_count__gte=2)
        .annotate(
            domain=Left(
                "canonical_story_url",
                Coalesce(
                    NullIf(StrIndex("canonical_story_url", Value("/")), 0) - 1,
                    Length("canonical_story_url"),
                ),
            ),
        )
        .values("domain")
        .annotate(
            comment_count=Sum("comment_count"),
            discussion_count=Count("platform_id"),
        )
        .order_by("-discussion_count")
    )

    return stats[:23]


@shared_task(ignore_result=True)
@celery_util.singleton(timeout=240, blocking_timeout=120)
def discussions_statistics():
    models.Statistics.update_platform_statistics(
        list(discussions_platform_statistics()),
    )
    models.Statistics.update_top_stories_statistics(
        list(discussions_top_stories()),
    )
    models.Statistics.update_top_domains_statistics(
        list(discussions_top_domains()),
    )
