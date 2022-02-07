from django.db import models
from django.contrib.postgres import fields as postgres_fields
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.contrib.postgres.search import TrigramWordBase
from django.contrib.postgres.search import SearchVectorField
# from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models.lookups import PostgresOperatorLookup
from django.contrib.postgres.search import SearchQuery, SearchRank
from . import discussions, tags, title, extract
from django.utils import timezone
import datetime
from django.core import serializers
import json
from dateutil import parser as dateutil_parser
from django.db.models import Sum, Value, Q, Count, Max, Min
from django.db.models import Subquery, OuterRef
# from django.db.models import Func, F
from django.db.models.functions import Round, Coalesce, Upper, Concat


class MyTrigramStrictWordSimilarity(TrigramWordBase):
    function = 'STRICT_WORD_SIMILARITY'


@models.CharField.register_lookup
class MyTrigramStrictWordSimilar(PostgresOperatorLookup):
    lookup_name = 'trigram_strict_word_similar'
    postgres_operator = '%%>>'


class Discussion(models.Model):
    class Meta:
        indexes = [
            # GinIndex(name='gin_discussion_title',
            #          fields=['title'],
            #          opclasses=['gin_trgm_ops']),
            # GinIndex(name='gin_discussion_norm_title',
            #          fields=['normalized_title'],
            #          opclasses=['gin_trgm_ops']),
            GinIndex(name='gin_discussion_vec_title',
                     fields=["title_vector"]),
            models.Index(OpClass(Upper('schemeless_story_url'),
                                 name='varchar_pattern_ops'),
                         name='index_schemeless_story_url'),
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
    scheme_of_story_url = models.CharField(max_length=25, null=True)
    """Original URL of the story without the scheme"""
    schemeless_story_url = models.CharField(max_length=100_000, null=True)
    canonical_story_url = models.CharField(max_length=100_000,
                                           blank=True,
                                           null=True)
    canonical_redirect_url = models.CharField(max_length=100_000,
                                              blank=True,
                                              default=None,
                                              null=True)

    title = models.CharField(max_length=2048, null=True)
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
        if not self.scheme_of_story_url or\
           not self.schemeless_story_url:
            return None

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
            (self.schemeless_story_url or ''), self.tags, stem=False)

        self.normalized_tags = tags.normalize(
            self.tags, self.platform, self.title, (self.schemeless_story_url or ''))

        if self.schemeless_story_url and len(self.schemeless_story_url) > 2700:
            self.schemeless_story_url = None
        if self.canonical_story_url and len(self.canonical_story_url) > 2700:
            self.canonical_story_url = None
        if not self.schemeless_story_url and not self.canonical_story_url:
            self.scheme_of_story_url = None

    def save(self, *args, **kwargs):
        self._pre_save()
        super(Discussion, self).save(*args, **kwargs)

    @property
    def id(self):
        return self.platform_id[1:]

    @property
    def subreddit(self):
        if self.platform == 'r':
            return self.tags[0]

    def subreddit_name(self):
        if self.platform == 'r':
            return f"/r/{self.subreddit}"

    def subreddit_url(
            self,
            preferred_external_url=discussions.PreferredExternalURL.Standard):
        if self.platform == 'r':
            return f"{self.platform_url(self.platform, preferred_external_url)}/r/{self.subreddit}"

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
        elif platform == 't':
            return 60
        elif platform == 's':
            return 70
        elif platform == 'e':
            return 80
        elif platform == 'a':
            return 90
        else:
            return 100

    @classmethod
    def platforms(
            cls,
            preferred_external_url=discussions.PreferredExternalURL.Standard):
        ps = {}
        for p in sorted(['h', 'u', 'r', 'l', 'b', 'g', 't', 's', 'e', 'a'],
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
        elif platform == 't':
            return "tilde news"
        elif platform == 's':
            return "Standard"
        elif platform == 'e':
            return "Echo JS"
        elif platform == 'a':
            return "Laarc"

    @classmethod
    def platform_url(cls, platform, preferred_external_url=discussions.PreferredExternalURL.Standard):
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
        elif platform == 't':
            return "https://tilde.news"
        elif platform == 's':
            return "https://std.bz"
        elif platform == 'e':
            return "https://echojs.com"
        elif platform == 'a':
            return "https://www.laarc.io"

    @classmethod
    def platform_tag_url(cls, platform, preferred_external_url):
        if platform == 'r':
            if preferred_external_url == discussions.PreferredExternalURL.Standard:
                return 'https://www.reddit.com/r'
            if preferred_external_url == discussions.PreferredExternalURL.Old:
                return 'https://old.reddit.com/r'
            if preferred_external_url == discussions.PreferredExternalURL.Mobile:
                return 'https://m.reddit.com/r'
        elif platform in ('l', 'b', 'g', 't', 's'):
            return cls.platform_url(platform, preferred_external_url) + '/t'
        elif platform in ('a'):
            return cls.platform_url(platform, preferred_external_url) + '/l'

        return None

    def score_label(self):
        if self.platform == 'u':
            return 'reads'
        return 'points'

    @property
    def discussion_url(
            self,
            preferred_external_url=discussions.PreferredExternalURL.Standard):
        bu = self.platform_url(self.platform, preferred_external_url)
        if self.platform == 'r':
            return f"{bu}/r/{self.subreddit}/comments/{self.id}"
        elif self.platform in ('h', 'a'):
            return f"{bu}/item?id={self.id}"
        elif self.platform == 'u':
            return f"{bu}/{self.id}"
        elif self.platform in ('l', 'b', 'g', 't', 's'):
            return f"{bu}/s/{self.id}"
        elif self.platform in ('e'):
            return f"{bu}/news/{self.id}"

    @classmethod
    def of_url(cls, url, client=None, only_relevant_stories=True):
        if not url:
            return cls.objects.none(), '', ''

        seven_days_ago = timezone.now() - datetime.timedelta(days=7)
        min_comments = 1

        scheme, url = discussions.split_scheme(url)
        cu = discussions.canonical_url(url)
        rcu = cu

        ds = (cls.objects.filter(schemeless_story_url__iexact=url)
              | cls.objects.filter(schemeless_story_url__iexact=cu)
              | cls.objects.filter(canonical_story_url=cu))

        ds = ds.exclude(schemeless_story_url__isnull=True)
        ds = ds.exclude(schemeless_story_url='')

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
    def counts_of_url(cls, url):
        if not url:
            return

        scheme, url = discussions.split_scheme(url)
        cu = discussions.canonical_url(url)
        rcu = cu

        dcs = (cls.objects.filter(schemeless_story_url__iexact=url)
               | cls.objects.filter(schemeless_story_url__iexact=cu)
               | cls.objects.filter(canonical_story_url=cu))

        dcs = dcs.aggregate(total_comments=Coalesce(Sum('comment_count'), Value(0)),
                            total_score=Coalesce(Sum('score'), Value(0)),
                            total_discussions=Coalesce(Count('platform_id'), Value(0)),
                            last_discussion=Max('created_at'),
                            first_discussion=Min('created_at'),
                            story_url=Concat(Max('scheme_of_story_url'),
                                             Value('://'),
                                             Max('schemeless_story_url')))

        return dcs, cu, rcu

    @classmethod
    def of_url_or_title(cls, url_or_title, client=None):
        if not url_or_title:
            return cls.objects.none(), '', ''

        seven_days_ago = timezone.now() - datetime.timedelta(days=7)
        min_comments = 2
        min_score = 2

        if not url_or_title:
            return None, None, None

        scheme, url = discussions.split_scheme(url_or_title)
        cu = discussions.canonical_url(url)
        rcu = cu

        ds = (cls.objects.filter(schemeless_story_url__iexact=url)
              | cls.objects.filter(schemeless_story_url__iexact=cu)
              | cls.objects.filter(canonical_story_url=cu))

        ds = ds.exclude(schemeless_story_url__isnull=True)
        ds = ds.exclude(schemeless_story_url='')

        ds = ds.annotate(search_rank=Value(1))

        ds = ds.filter(
            Q(comment_count__gte=min_comments)
            | Q(created_at__gt=seven_days_ago)
            | Q(platform='u'))

        # ds = ds[:50]

        ts = None

        if scheme not in ('http', 'https', 'ftp'):
            # xojoc: test search with:
            #   https://discu.eu/q/APL%20in%20JavaScript
            #   https://discu.eu/q/Go%201.4.1%20has%20been%20released
            #   https://discu.eu/q/The%20Gosu%20Programming%20Language
            #   https://discu.eu/q/F-35%20C%2B%2B%20coding%20standard%20%5Bpdf%5D
            #   https://discu.eu/q/The%20Carnap%20Programming%20Language
            #   https://discu.eu/?q=For+C+programmers+that+hate+C%2B%2B+%282011%29

            query = url_or_title
            site_prefix = 'site:'
            tokens = url_or_title.split()

            if tokens[0].startswith(site_prefix) and len(tokens[0]) > len(site_prefix):
                query = ' '.join(tokens[1:])

                url_prefix = tokens[0][len(site_prefix):].lower()
                curl_prefix = discussions.canonical_url(url_prefix, generic=True)

                ts = (cls.objects.filter(schemeless_story_url__iexact=url_prefix) |
                      cls.objects.filter(schemeless_story_url__iexact=url_prefix) |
                      cls.objects.filter(canonical_story_url=curl_prefix) |
                      cls.objects.filter(schemeless_story_url__istartswith=url_prefix) |
                      cls.objects.filter(schemeless_story_url__istartswith=curl_prefix) |
                      cls.objects.filter(canonical_story_url__startswith=url_prefix) |
                      cls.objects.filter(canonical_story_url__startswith=curl_prefix))

            if len(query) > 1:
                q = title.normalize(query, stem=False)
                psq = SearchQuery(q, search_type='plain')

                base = cls.objects
                if ts is not None:
                    base = ts

                ts = base.annotate(search_rank=Round(SearchRank('title_vector', psq), 2))
                ts = ts.filter(title_vector=psq)
            else:
                if ts is not None:
                    ts = ts.annotate(search_rank=Value(1))

            if ts is not None:
                ts = ts.filter(
                    (Q(comment_count__gte=min_comments) & Q(score__gte=min_score))
                    | Q(created_at__gt=seven_days_ago)
                    | Q(platform='u'))
                ts = ts.exclude(schemeless_story_url__isnull=True)
                ts = ts.exclude(schemeless_story_url='')

                ts = ts[:30]

        if ts is not None:
            ds = ds.union(ts)

        ds = ds.order_by('-search_rank', '-created_at', '-platform_id')

        ds = ds[:50]

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


class MastodonPost(models.Model):
    post_id = models.BigIntegerField(primary_key=True, null=False)
    bot_names = postgres_fields.ArrayField(models.CharField(max_length=255),
                                           null=True,
                                           blank=True,
                                           default=list)

    discussions = models.ManyToManyField(Discussion)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


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
    normalized_title = models.CharField(max_length=2048, null=True, blank=True)

    tags = postgres_fields.ArrayField(models.CharField(max_length=255,
                                                       blank=True),
                                      null=True,
                                      blank=True)

    normalized_tags = postgres_fields.ArrayField(models.CharField(max_length=255,
                                                                  blank=True),
                                                 null=True,
                                                 blank=True)

    clean_html = models.TextField(null=True)

    excerpt = models.TextField(null=True)

    last_fetch = models.DateTimeField(null=True)
    last_processed = models.DateTimeField(null=True)

    status_code = models.IntegerField(null=True)

    links = models.ManyToManyField('self',
                                   symmetrical=False,
                                   through='Link',
                                   related_name='inbound_link')

    @property
    def complete_url(self):
        return self.scheme + '://' + self.url

    @classmethod
    def by_url(cls, url):
        if not url:
            return None

        scheme, url = discussions.split_scheme(url)
        cu = discussions.canonical_url(url)

        r = (cls.objects.filter(url=url) |
             cls.objects.filter(url=cu) |
             cls.objects.filter(canonical_url=cu)).first()

        return r

    def inbound_resources(self):
        ils = self.inbound_link.all().distinct()
        ils = ils.annotate(
            discussions_comment_count=Coalesce(
                Subquery(
                    Discussion.objects
                    .filter(canonical_story_url=OuterRef('canonical_url'))
                    .values('canonical_story_url')
                    .annotate(comment_count=Sum('comment_count'))
                    .values('comment_count')),
                Value(0)))
        # ils = ils.annotate(
        #     discussions_normalized_tags=Subquery(
        #         Discussion.objects
        #         .filter(canonical_story_url=OuterRef('canonical_url'))
        #         .values('canonical_story_url')
        #         .annotate(unnest_tags=Subquery(
        #             Discussion.objects
        #             .filter(canonical_story_url=OuterRef('canonical_story_url'))
        #             .annotate(normalized_tag=Func(F('normalized_tags'),
        #                                           function='unnest'))))
        #         .aggregate(normalized_tags=ArrayAgg('unnest_tags')
        #                    )))
        # ils = ils.annotate(
        #     discussions_normalized_tags=Subquery(
        #         Discussion.objects
        #         .filter(canonical_story_url=OuterRef('canonical_url'))
        #         .values('canonical_story_url')
        #         .annotate(normalized_tag=Func(F('normalized_tags'),
        #                                       function='unnest'))
        #         .annotate(normalized_tags=ArrayAgg('normalized_tag'))
        #         .values('normalized_tags')))

        # discussions_normalized_tags=ArrayAgg(Subquery(
        #     Discussion.objects
        #     .filter(canonical_story_url=OuterRef('canonical_url'))
        #     .values('canonical_story_url')
        #     .annotate(normalized_tags=Func(F('normalized_tags'),
        #                                    function='unnest'))
        #     .values_list('normalized_tags', flat=True))))

        ils = ils.order_by('-discussions_comment_count')

        return ils

    @property
    def author(self):
        # for now extract at runtime. In the future possibly add to the model
        if self.clean_html:
            s = extract.structure(self.clean_html)
            if s:
                return s.author

        return extract.Author()


class Link(models.Model):
    from_resource = models.ForeignKey(Resource,
                                      on_delete=models.CASCADE,
                                      related_name='from_resource')
    to_resource = models.ForeignKey(Resource,
                                    on_delete=models.CASCADE,
                                    related_name='to_resource')

    anchor_title = models.TextField(null=True)
    anchor_text = models.TextField(null=True)
    anchor_rel = models.TextField(null=True)


# class HackerNewsItem(models.Model):
#     class Type(models.TextChoices):
#         COMMENT = 'c'
#         STORY = 's'


#     id = models.BigAutoField(primary_key=True)

#     parent = models.ForeignKey('self')

#     type = models.CharField(max_length=1, choices = Type.choices)


class APIClient(models.Model):
    name = models.TextField()
    token = models.TextField(null=True, blank=True)
    limited = models.BooleanField(default=False)
    email = models.TextField(null=True, blank=True)
    url = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.email}"

    @classmethod
    def generate_token(cls):
        import secrets
        return secrets.token_urlsafe(32)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        super(APIClient, self).save(*args, **kwargs)
