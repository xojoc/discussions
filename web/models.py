from django.db import models
from django.contrib.postgres import fields as postgres_fields
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import TrigramWordBase
from django.contrib.postgres.search import SearchVectorField
from django.db.models.lookups import PostgresOperatorLookup
from django.contrib.postgres.search import SearchQuery, SearchRank
from . import discussions, tags, title
from django.utils import timezone
import datetime
from django.core import serializers
import json
from dateutil import parser as dateutil_parser
from django.db.models import Value, Q
from django.db.models.functions import Round


class MyTrigramStrictWordSimilarity(TrigramWordBase):
    function = 'STRICT_WORD_SIMILARITY'


@models.CharField.register_lookup
class MyTrigramStrictWordSimilar(PostgresOperatorLookup):
    lookup_name = 'trigram_strict_word_similar'
    postgres_operator = '%%>>'


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
            models.Index(name='index_schemeless_story_url',
                         fields=['schemeless_story_url'],
                         opclasses=['varchar_pattern_ops']),
            models.Index(name='index_canonical_story_url',
                         fields=['canonical_story_url'],
                         opclasses=['varchar_pattern_ops']),
            models.Index(name='index_canonical_redirect_url',
                         fields=['canonical_redirect_url'],
                         opclasses=['varchar_pattern_ops']),
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

    def _pre_save(self):
        if not self.platform:
            self.platform = self.platform_id[0]

        if not self.canonical_story_url:
            self.canonical_story_url = self.schemeless_story_url

        if (self.canonical_redirect_url == self.canonical_story_url
                or self.canonical_redirect_url == self.schemeless_story_url):
            self.canonical_redirect_url = None

        self.normalized_title = title.normalize(
            self.title, self.platform,
            self.schemeless_story_url, self.tags, stem=False)

        self.normalized_tags = tags.normalize(
            self.tags, self.platform, self.title, self.schemeless_story_url)

    def save(self, *args, **kwargs):
        self._pre_save()
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

        site_prefix = 'site:'
        if url_or_title.startswith(site_prefix) and\
           ' ' not in url_or_title and\
           len(url_or_title) > len(site_prefix):

            url_prefix = url_or_title[len(site_prefix):]
            ds = (cls.objects.filter(schemeless_story_url=url_prefix) |
                  cls.objects.filter(canonical_story_url=url_prefix) |
                  cls.objects.filter(schemeless_story_url__startswith=url_prefix))

            ds = ds.filter(
                Q(comment_count__gte=min_comments)
                | Q(created_at__gt=seven_days_ago)
                | Q(platform='u'))
        else:
            ds = (cls.objects.filter(schemeless_story_url=url)
                  | cls.objects.filter(schemeless_story_url=cu)
                  | cls.objects.filter(canonical_story_url=cu))

            ds = ds.filter(
                Q(comment_count__gte=min_comments)
                | Q(created_at__gt=seven_days_ago)
                | Q(platform='u'))

        # ds = ds.annotate(word_similarity=Value(99))
        ds = ds.annotate(search_rank=Value(1))

        if len(url_or_title) > 3 and not (
                url_or_title.lower().startswith('http:')
                or url_or_title.lower().startswith('https:')):

            # xojoc: test search with:
            #   https://discu.eu/q/APL%20in%20JavaScript
            #   https://discu.eu/q/Go%201.4.1%20has%20been%20released
            #   https://discu.eu/q/The%20Gosu%20Programming%20Language
            #   https://discu.eu/q/F-35%20C%2B%2B%20coding%20standard%20%5Bpdf%5D
            #   https://discu.eu/q/The%20Carnap%20Programming%20Language
            #   https://discu.eu/?q=For+C+programmers+that+hate+C%2B%2B+%282011%29

            q = title.normalize(url_or_title, stem=False)

            wsq = SearchQuery(q, search_type='websearch')
            psq = SearchQuery(q, search_type='plain')
            # normalized_title = title.normalize(url_or_title, stem=True)

            ts = cls.objects.annotate(search_rank=Round(SearchRank('title_vector', psq), 2))
            # annotate(word_similarity=Round(
            #     MyTrigramStrictWordSimilarity(normalized_title, 'title'), 2))

            # ts = ts.filter(title__trigram_strict_word_similar=normalized_title)
            ts = ts.filter(Q(title_vector=wsq) | Q(title_vector=psq))

            # xojoc: this is needed to filter out sensless results non
            # filtered out by the trigram filter. Example: "APL in JavaScript"
            # ts = ts.filter(search_rank__gt=0.2)

            ts = ts.filter(
                Q(comment_count__gte=min_comments)
                | Q(created_at__gt=seven_days_ago)
                | Q(platform='u'))

            # ts = ts.order_by('-word_similarity')
            ts = ts.order_by('-search_rank')

            ts = ts[:23]

            ds = ds.union(ts)

        ds = ds.order_by('-search_rank', '-created_at',
                         '-platform_id')

        return ds, cu, rcu

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
    bot_names = postgres_fields.ArrayField(models.CharField(max_length=255),
                                           null=True,
                                           blank=True,
                                           default=list)

    discussions = models.ManyToManyField(Discussion)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.bot_name:
            self.bot_names = (self.bot_names or []).append(self.bot_name)

        self.bot_names = sorted(set(self.bot_names or []))

        super(Tweet, self).save(*args, **kwargs)


class Resource(models.Model):
    class Meta:
        indexes = [
            models.Index(name='index_url',
                         fields=['url'],
                         opclasses=['varchar_pattern_ops']),
            models.Index(name='index_canonical_url',
                         fields=['canonical_url'],
                         opclasses=['varchar_pattern_ops'])
        ]

    id = models.BigAutoField(primary_key=True)

    scheme = models.CharField(max_length=25)

    url = models.CharField(max_length=100_000,
                           blank=True,
                           default=None,
                           null=True)

    canonical_url = models.CharField(max_length=100_000,
                                     blank=True,
                                     null=True)

    title = models.CharField(max_length=2048, null=True)

    normalized_tags = postgres_fields.ArrayField(models.CharField(max_length=255,
                                                                  blank=True),
                                                 null=True,
                                                 blank=True)

    clean_html = models.TextField(null=True)

    excerpt = models.TextField(null=True)

    last_fetch = models.DateTimeField(null=True)

    status_code = models.IntegerField(null=True)

    @classmethod
    def by_url(cls, url):
        scheme, url = discussions.split_scheme(url)
        cu = discussions.canonical_url(url)

        r = (cls.objects.filter(url=url) |
             cls.objects.filter(url=cu) |
             cls.objects.filter(canonical_url=cu)).first()

        return r
