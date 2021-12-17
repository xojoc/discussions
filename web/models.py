from django.db import models
from django.contrib.postgres import fields as postgres_fields
from django.contrib.postgres.indexes import GinIndex
# from django.contrib.postgres.search import TrigramWordSimilarity,
from django.contrib.postgres.search import SearchVectorField, SearchQuery, SearchRank
from . import discussions, tags, title
from django.utils import timezone
import datetime
from django.core import serializers
import json
from dateutil import parser as dateutil_parser
from django.db.models import Value, Q
from django.db.models.functions import Round


class Discussion(models.Model):
    class Meta:
        indexes = [
            GinIndex(name='gin_discussion_title',
                     fields=['title'],
                     opclasses=['gin_trgm_ops']),
            GinIndex(name='gin_discussion_norm_title',
                     fields=['normalized_title'],
                     opclasses=['gin_trgm_ops']),
            GinIndex(name='gin_discussion_vec_title',
                     fields=["title_vector"]),
            models.Index(fields=['schemeless_story_url']),
            models.Index(fields=['canonical_story_url']),
            models.Index(fields=['canonical_redirect_url']),
            models.Index(fields=['created_at'])
        ]

    platform_id = models.CharField(primary_key=True, max_length=255)
    platform = models.CharField(max_length=1, blank=False)
    created_at = models.DateTimeField(null=True)
    scheme_of_story_url = models.CharField(max_length=25)
    """Original URL of the story without the scheme"""
    schemeless_story_url = models.CharField(max_length=100_000)
    canonical_story_url = models.CharField(max_length=100_000,
                                           blank=True,
                                           null=True)
    canonical_redirect_url = models.CharField(max_length=100_000,
                                              blank=True,
                                              default=None,
                                              null=True)

    title = models.CharField(max_length=2048)
    normalized_title = models.CharField(max_length=2048, null=True, blank=True)
    title_vector = SearchVectorField(null=True)

    comment_count = models.IntegerField(default=0)
    score = models.IntegerField(default=0, null=True)
    """In case of Reddit tags will have only one entry which represents the subreddit"""
    tags = postgres_fields.ArrayField(models.CharField(max_length=255,
                                                       blank=True),
                                      null=True,
                                      blank=True)

    normalized_tags = postgres_fields.ArrayField(models.CharField(max_length=255,
                                                                  blank=True),
                                                 null=True,
                                                 blank=True)

    archived = models.BooleanField(default=False)

    entry_created_at = models.DateTimeField(auto_now_add=True)
    entry_updated_at = models.DateTimeField(auto_now=True)

    @property
    def story_url(self):
        return f"{self.scheme_of_story_url}://{self.schemeless_story_url}"

    def __str__(self):
        return f"{self.platform_id} - {self.story_url}"

    @property
    def domain(self):
        url = self.canonical_story_url
        if not url:
            url = self.schemeless_story_url

        if not url:
            return None

        return url.split('/')[0]

    def save(self, *args, **kwargs):
        if not self.platform:
            self.platform = self.platform_id[0]

        if not self.canonical_story_url:
            self.canonical_story_url = self.schemeless_story_url

        if (self.canonical_redirect_url == self.canonical_story_url
                or self.canonical_redirect_url == self.schemeless_story_url):
            self.canonical_redirect_url = None

        self.normalized_title = title.normalize(
            self.title, self.platform,  self.schemeless_story_url, self.tags)

        self.normalized_tags = tags.normalize(
            self.tags, self.platform, self.normalized_title, self.schemeless_story_url)

        super(Discussion, self).save(*args, **kwargs)

    @property
    def id(self):
        return self.platform_id[1:]

    @property
    def subreddit(self):
        return self.tags[0]

    @classmethod
    def platform_order(self, platform):
        if platform == 'h':
            return 10
        elif platform == 'u':
            return 15
        elif platform == 'r':
            return 20
        elif platform == 'l':
            return 30
        elif platform == 'b':
            return 40
        elif platform == 'g':
            return 50
        else:
            return 100

    @classmethod
    def platforms(
            cls,
            preferred_external_url=discussions.PreferredExternalURL.Standard):
        ps = {}
        for p in sorted(['h', 'u', 'r', 'l', 'b', 'g'],
                        key=lambda x: cls.platform_order(x)):
            ps[p] = (cls.platform_name(p),
                     cls.platform_url(p, preferred_external_url))
        return ps

    @classmethod
    def platform_name(cls, platform):
        if platform == 'h':
            return 'Hacker News'
        elif platform == 'u':
            return 'Lambda the Ultimate'
        elif platform == 'r':
            return 'Reddit'
        elif platform == 'l':
            return 'Lobsters'
        elif platform == 'b':
            return 'Barnacles'
        elif platform == 'g':
            return "Gambero"

    @classmethod
    def platform_url(cls, platform, preferred_external_url):
        if platform == 'r':
            if preferred_external_url == discussions.PreferredExternalURL.Standard:
                return 'https://www.reddit.com'
            if preferred_external_url == discussions.PreferredExternalURL.Old:
                return 'https://old.reddit.com'
            if preferred_external_url == discussions.PreferredExternalURL.Mobile:
                return 'https://m.reddit.com'
        elif platform == 'h':
            return "https://news.ycombinator.com"
        elif platform == 'u':
            return "http://lambda-the-ultimate.org"
        elif platform == 'l':
            return "https://lobste.rs"
        elif platform == 'b':
            return "https://barnacl.es"
        elif platform == 'g':
            return "https://gambe.ro"

    @classmethod
    def platform_tag_url(cls, platform, preferred_external_url):
        if platform == 'r':
            if preferred_external_url == discussions.PreferredExternalURL.Standard:
                return 'https://www.reddit.com/r'
            if preferred_external_url == discussions.PreferredExternalURL.Old:
                return 'https://old.reddit.com/r'
            if preferred_external_url == discussions.PreferredExternalURL.Mobile:
                return 'https://m.reddit.com/r'
        elif platform == 'l':
            return "https://lobste.rs/t"
        elif platform == 'b':
            return "https://barnacl.es/t"
        elif platform == 'g':
            return "https://gambe.ro/t"

        return None

    def score_label(self):
        if self.platform == 'u':
            return 'reads'
        return 'points'

    def discussion_url(
            self,
            preferred_external_url=discussions.PreferredExternalURL.Standard):
        bu = self.platform_url(self.platform, preferred_external_url)
        if self.platform == 'r':
            return f"{bu}/r/{self.subreddit}/comments/{self.id}"
        elif self.platform == 'h':
            return f"{bu}/item?id={self.id}"
        elif self.platform == 'u':
            return f"{bu}/{self.id}"
        elif self.platform in ('l', 'b', 'g'):
            return f"{bu}/s/{self.id}"

    def subreddit_name(self):
        return f"/r/{self.subreddit}"

    def subreddit_url(
            self,
            preferred_external_url=discussions.PreferredExternalURL.Standard):
        return f"{self.platform_url(self.platform, preferred_external_url)}/r/{self.subreddit}"

    @classmethod
    def of_url(cls, url, client=None, only_relevant_stories=True):
        seven_days_ago = timezone.now() - datetime.timedelta(days=7)
        min_comments = 1

        scheme, url = discussions.split_scheme(url)
        cu = discussions.canonical_url(url)
        rcu = cu

        ds = (cls.objects.filter(schemeless_story_url=url)
              | cls.objects.filter(schemeless_story_url=cu)
              | cls.objects.filter(canonical_story_url=cu))

        if only_relevant_stories:
            ds = ds.filter(
                Q(comment_count__gte=min_comments)
                | Q(created_at__gt=seven_days_ago)
                | Q(platform='u'))

        ds = ds.annotate(word_similarity=Value(99))

        ds = ds.order_by('platform', '-word_similarity', '-created_at',
                         '-platform_id')

        return ds, cu, rcu

    @classmethod
    def of_url_or_title(cls, url_or_title, client=None):
        seven_days_ago = timezone.now() - datetime.timedelta(days=7)
        min_comments = 2

        scheme, url = discussions.split_scheme(url_or_title)
        cu = discussions.canonical_url(url)
        rcu = cu

        ds = (cls.objects.filter(schemeless_story_url=url)
              | cls.objects.filter(schemeless_story_url=cu)
              | cls.objects.filter(canonical_story_url=cu))

        ds = ds.filter(
            Q(comment_count__gte=min_comments)
            | Q(created_at__gt=seven_days_ago)
            | Q(platform='u'))

        ds = ds.annotate(word_similarity=Value(99))

        if len(url_or_title) > 3 and not (
                url_or_title.lower().startswith('http:')
                or url_or_title.lower().startswith('https:')):

            sq = SearchQuery(url_or_title, search_type='websearch')

            ts = cls.objects.\
                annotate(word_similarity=Round(
                    SearchRank('title_vector', sq), 2))

            ts = ts.filter(title_vector=sq)

            # ts = cls.objects.\
            #     annotate(word_similarity=Round(
            #         TrigramWordSimilarity(url_or_title, 'title'), 2))

            # ts = ts.filter(title__trigram_word_similar=url_or_title)

            ts = ts.filter(
                Q(comment_count__gte=min_comments)
                | Q(created_at__gt=seven_days_ago)
                | Q(platform='u'))

            # xojoc: disable for now since it messes with the PostgreSQL query planner
            # ts = ts[:20]

            ds = ds.union(ts)

        ds = ds.order_by('platform', '-word_similarity', '-created_at',
                         '-platform_id')

        return ds, cu, rcu

        # uds, cu, rcu = Discussion.of_url(url_or_title)
        # tds = Discussion.objects.none()
        # if len(url_or_title) > 3 and \
        #    '/' not in url_or_title and \
        #    not url_or_title.startswith('http:') and \
        #    not url_or_title.startswith('https:'):

        #     tds = Discussion.of_title(url_or_title)
        # return uds, tds, cu, rcu

    @classmethod
    def of_title(cls, title, client=None):
        pass
        # ds = (cls.objects.filter(schemeless_story_url=url) |
        #       cls.objects.filter(schemeless_story_url=cu) |
        #       # cls.objects.filter(schemeless_story_url=rcu) |
        #       cls.objects.filter(canonical_story_url=cu)
        #       # cls.objects.filter(canonical_redirect_url=rcu)
        #       ).\
        #     order_by('platform', '-created_at', 'tags__0', '-platform_id')

        # return ds, cu, rcu

        # tds = cls.objects.\
        #     annotate(canonical_url=Coalesce('canonical_story_url',
        #                                     'schemeless_story_url'),
        #              word_similarity=Round(TrigramWordSimilarity(title, 'title'), 2)).\
        #     values('canonical_url').\
        #     filter(title__trigram_word_similar=title).\
        #     annotate(comment_count=Sum('comment_count'),
        #              title=Max('title'),
        #              date__last_discussion=Max('created_at'),
        #              story_url=Max('schemeless_story_url'),
        #              word_similarity=Max('word_similarity')).\
        #     filter(comment_count__gt=3).\
        #     order_by('-word_similarity', '-comment_count')

        # return tds

    @classmethod
    def delete_useless_discussions(cls):
        six_months_ago = timezone.now() - datetime.timedelta(days=30 * 6)
        (cls.objects.filter(comment_count=0).filter(
            created_at__lte=six_months_ago)).delete()


class StatisticsDecoder(json.JSONDecoder):
    def __init__(self):
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object)

    def dict_to_object(self, d):
        for k in d:
            if k.startswith("date__"):
                d[k] = dateutil_parser.parse(d[k])

        return d


class Statistics(models.Model):
    name = models.CharField(primary_key=True, max_length=100)
    statistics = models.JSONField(encoder=serializers.json.DjangoJSONEncoder,
                                  decoder=StatisticsDecoder)

    @classmethod
    def update_platform_statistics(cls, statistics):
        cls.objects.update_or_create(
            name='platform', defaults={'statistics': {
                'data': statistics
            }})

    @classmethod
    def update_top_stories_statistics(cls, statistics):
        cls.objects.update_or_create(
            name='top_stories', defaults={'statistics': {
                'data': statistics
            }})

    @classmethod
    def update_top_domains_statistics(cls, statistics):
        cls.objects.update_or_create(
            name='top_domains', defaults={'statistics': {
                'data': statistics
            }})

    @classmethod
    def platform_statistics(cls):
        try:
            return cls.objects.get(name='platform').statistics['data']
        except cls.DoesNotExist:
            return []

    @classmethod
    def top_stories_statistics(cls):
        try:
            return cls.objects.get(name='top_stories').statistics['data']
        except cls.DoesNotExist:
            return []

    @classmethod
    def top_domains_statistics(cls):
        try:
            return cls.objects.get(name='top_domains').statistics['data']
        except cls.DoesNotExist:
            return []

    @classmethod
    def all_statistics(cls):
        return {
            'platform': cls.platform_statistics(),
            'top_stories': cls.top_stories_statistics(),
            'top_domains': cls.top_domains_statistics()
        }


class Tweet(models.Model):
    tweet_id = models.BigIntegerField(primary_key=True, null=False)
    bot_name = models.CharField(max_length=255)

    discussions = models.ManyToManyField(Discussion)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
