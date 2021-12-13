from django.contrib.sitemaps import Sitemap
from .models import Discussion
from django.db.models import Sum, Count, Max
from . import util


class DiscussionsSitemap(Sitemap):
    protocol = 'https'
    limit = 10_000

    def items(self):
        return Discussion.objects.\
            exclude(canonical_story_url__isnull=True).\
            values('canonical_story_url').\
            annotate(comment_count=Sum('comment_count'),
                     discussion_count=Count('platform_id'),
                     entry_updated_at=Max('entry_updated_at'),
                     scheme_of_story_url=Max('scheme_of_story_url')). \
            order_by('canonical_story_url')

    def lastmod(self, obj):
        return obj['entry_updated_at']

    def location(self, obj):
        url = obj['scheme_of_story_url'] + '://' + obj['canonical_story_url']
        return util.discussions_canonical_url(url, with_domain=False)
