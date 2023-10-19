# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from typing_extensions import override

from . import topics, util, weekly
from .models import Discussion


class StaticViewSitemap(Sitemap):
    protocol = "https"

    @override
    def items(self):
        return [
            "web:api",
            "web:bookmarklet",
            "web:extension",
            "web:mentions",
            "web:pricing",
            "web:search",
            "web:social",
            "web:statistics",
            "web:website",
            "web:weekly_index",
        ]

    @override
    def location(self, item):
        return reverse(item)


class WeeklySitemap(Sitemap):
    protocol = "https"

    @override
    def items(self):
        its = []
        for topic_key in topics.topics:
            its.append(("web:weekly_topic", [topic_key]))
            for yearweek in weekly.last_nth_yearweeks(topic_key, 3):
                its.append(  # noqa: PERF401
                    (
                        "web:weekly_topic_week",
                        [topic_key, yearweek[0], yearweek[1]],
                    ),
                )

        return its

    @override
    def location(self, item):
        return reverse(item[0], args=item[1])


class DiscussionsSitemap(Sitemap):
    protocol = "https"
    limit = 10_000

    @override
    def items(self):
        return (
            Discussion.objects.exclude(scheme_of_story_url__isnull=True)
            .exclude(canonical_story_url__isnull=True)
            .filter(comment_count__gte=5)
            .order_by("pk")
        )

        # xojoc: fixme: Group By is too slow. Disabled for now.
        #        fix extraction when the single page model will be introduced

        # annotate(comment_count=Sum('comment_count'),

    # def lastmod(self, obj):

    @override
    def location(self, obj):
        url = obj.scheme_of_story_url + "://" + obj.canonical_story_url
        return util.discussions_canonical_url(url, with_domain=False)
