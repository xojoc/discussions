from django.contrib.sitemaps import Sitemap
from django.urls import reverse

# from django.db.models import Sum, Count, Max
from . import topics, util, weekly
from .models import Discussion


class StaticViewSitemap(Sitemap):
    protocol = "https"

    def items(self):
        return [
            "web:bookmarklet",
            "web:extension",
            "web:social",
            "web:statistics",
            "web:website",
            "web:weekly_index",
            "api-v0:openapi-swagger",
        ]

    def location(self, item):
        return reverse(item)


class WeeklySitemap(Sitemap):
    protocol = "https"

    def items(self):
        its = []
        for topic_key in topics.topics:
            its.append(("web:weekly_topic", [topic_key]))
            for yearweek in weekly.last_nth_yearweeks(topic_key, 10):
                its.append(
                    (
                        "web:weekly_topic_week",
                        [topic_key, yearweek[0], yearweek[1]],
                    )
                )

        return its

    def location(self, item):
        return reverse(item[0], args=item[1])


class DiscussionsSitemap(Sitemap):
    protocol = "https"
    limit = 10_000

    def items(self):
        q = (
            Discussion.objects.exclude(scheme_of_story_url__isnull=True)
            .exclude(canonical_story_url__isnull=True)
            .filter(comment_count__gte=5)
            .order_by("pk")
        )

        # xojoc: fixme: Group By is too slow. Disabled for now.
        #        fix extraction when the single page model will be introduced

        # exclude(canonical_story_url__isnull=True).\
        # values('canonical_story_url').\
        # annotate(comment_count=Sum('comment_count'),
        #          discussion_count=Count('platform_id'),
        #          entry_updated_at=Max('entry_updated_at'),
        #          scheme_of_story_url=Max('scheme_of_story_url')).\
        # filter(comment_count__gte=5).\
        # order_by('canonical_story_url')

        return q

    # def lastmod(self, obj):
    #     return obj.entry_updated_at

    def location(self, obj):
        url = obj.scheme_of_story_url + "://" + obj.canonical_story_url
        return util.discussions_canonical_url(url, with_domain=False)
