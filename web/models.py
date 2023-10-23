# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import contextlib
import datetime
import json
import secrets
import urllib
import urllib.parse
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Self

import cleanurl
import django.template.loader as template_loader
from dateutil import parser as dateutil_parser
from django import forms
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres import fields as postgres_fields
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVectorField,
)
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Round, Upper
from django.utils import timezone
from django_stubs_ext.db.models import TypedModelMeta
from typing_extensions import override

from web import api_statistics, mastodon_api
from web.category import Category
from web.platform import Platform

from . import (
    email_util,
    extract,
    tags,
    title,
    topics,
    twitter_api,
)

if TYPE_CHECKING:
    from allauth.account import models as allauth_models


class _CustomArrayField(postgres_fields.ArrayField):
    @override
    def formfield(self, **kwargs):
        defaults = {
            "choices_form_class": forms.TypedMultipleChoiceField,
            "choices": self.base_field.choices,
            "coerce": self.base_field.to_python,
            "widget": forms.CheckboxSelectMultiple
            if self.base_field.choices
            else None,
        }

        defaults.update(kwargs)
        return super().formfield(**defaults)

    @override
    def validate(self, value, model_instance):
        # Validate value one by one if list
        if isinstance(value, list):
            for single_value in value:
                self.base_field.validate(single_value, model_instance)
        else:
            super().validate(value, model_instance)


class Discussion(models.Model):
    """Threads and posts on various platforms with metadata.

    Attributes:
        normalized_title: normalized title to help lookups
        normalized_tags: normalized tags to help lookups
        category: categorize the discussion
    """

    platform_id = models.CharField(primary_key=True, max_length=255)
    _platform = models.CharField(max_length=1, blank=False)
    created_at = models.DateTimeField(null=True)
    scheme_of_story_url = models.CharField(  # noqa: DJ001
        max_length=25,
        null=True,
    )
    """Original URL of the story without the scheme"""
    schemeless_story_url = models.CharField(  # noqa: DJ001
        max_length=100_000,
        null=True,
    )
    canonical_story_url = models.CharField(  # noqa: DJ001
        max_length=100_000,
        blank=True,
        null=True,
    )
    canonical_redirect_url = models.CharField(  # noqa: DJ001
        max_length=100_000,
        blank=True,
        null=True,
    )

    title = models.CharField(max_length=2048)
    normalized_title = models.CharField(max_length=2048, blank=True)
    title_vector = SearchVectorField(null=True)

    comment_count = models.IntegerField(default=0)
    score = models.IntegerField(default=0, null=True)
    """In case of Reddit tags will have only one entry """
    """which represents the subreddit"""
    tags = postgres_fields.ArrayField(
        models.CharField(max_length=255, blank=True),
        blank=True,
    )

    normalized_tags = postgres_fields.ArrayField(
        models.CharField(max_length=255, blank=True),
        blank=True,
    )

    _category = models.IntegerField(default=Category.ARTICLE.value)

    archived = models.BooleanField(default=False)

    tweet_set: models.Manager["Tweet"]
    mastodonpost_set: models.Manager["MastodonPost"]

    entry_created_at = models.DateTimeField(auto_now_add=True)
    entry_updated_at = models.DateTimeField(auto_now=True)

    class Meta(TypedModelMeta):
        indexes: Sequence[models.Index] = [
            GinIndex(name="gin_discussion_vec_title", fields=["title_vector"]),
            models.Index(
                OpClass(
                    Upper("schemeless_story_url"),
                    name="varchar_pattern_ops",
                ),
                name="index_schemeless_story_url",
            ),
            models.Index(
                name="index_canonical_story_url",
                fields=["canonical_story_url"],
                opclasses=["varchar_pattern_ops"],
            ),
            models.Index(
                name="index_canonical_redirect_url",
                fields=["canonical_redirect_url"],
                opclasses=["varchar_pattern_ops"],
            ),
            models.Index(fields=["created_at"]),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.platform_id} - {self.story_url}"

    @override
    def save(self, *args, **kwargs):
        self.pre_save()
        super().save(*args, **kwargs)

    def pre_save(self):
        if self.title:
            self.title = self.title.replace("\x00", "")

        if not self._platform:
            self._platform = self.platform_id[0]

        if self.schemeless_story_url:
            u = cleanurl.cleanurl("//" + self.schemeless_story_url)
            if u:
                self.canonical_story_url = u.schemeless_url
            else:
                self.canonical_story_url = None

        if not self.canonical_story_url:
            self.canonical_story_url = self.schemeless_story_url

        if self.canonical_redirect_url in {
            self.canonical_story_url,
            self.schemeless_story_url,
        }:
            self.canonical_redirect_url = None

        url_max_len = 2700
        if (
            self.schemeless_story_url
            and len(self.schemeless_story_url) > url_max_len
        ):
            self.schemeless_story_url = None
        if (
            self.canonical_story_url
            and len(self.canonical_story_url) > url_max_len
        ):
            self.canonical_story_url = None
        if not self.schemeless_story_url and not self.canonical_story_url:
            self.scheme_of_story_url = None

        self.tags = self.tags or []

        self.normalized_title = title.normalize(
            self.title,
            self.platform,
            (self.story_url or ""),
            self.tags,
            stem=False,
        )

        self.normalized_tags = tags.normalize(
            self.tags,
            self.platform,
            self.title,
            (self.story_url or ""),
        )

        self.normalized_tags = sorted(self.normalized_tags or [])

        self._category = Category.derive(
            self.title,
            self.canonical_story_url or "",
            self.normalized_tags,
            self.platform,
        ).value

    @property
    def platform(self):
        return Platform(self._platform)

    @property
    def category(self):
        return Category(self._category)

    @property
    def story_url(self):
        if not self.scheme_of_story_url or not self.schemeless_story_url:
            return None

        return f"{self.scheme_of_story_url}://{self.schemeless_story_url}"

    @property
    def domain(self):
        url = self.canonical_story_url
        if not url:
            url = self.schemeless_story_url

        if not url:
            return None

        return url.split("/")[0]

    @property
    def id(self):  # noqa: A003
        return self.platform_id[1:]

    @property
    def subreddit(self):
        if self.platform == Platform.REDDIT:
            return self.tags[0]
        return None

    def subreddit_name(self):
        if self.platform == Platform.REDDIT:
            return f"/r/{self.subreddit}"
        return None

    def subreddit_url(self):
        if self.platform == Platform.REDDIT:
            return f"{self.platform.url}/r/{self.subreddit}"
        return None

    @property
    def discussion_url(self):
        return self.platform.thread_url(self.id, self.subreddit)

    @classmethod
    def of_url(cls, url, *, only_relevant_stories=True):
        if not url:
            return cls.objects.none(), "", ""

        seven_days_ago = timezone.now() - datetime.timedelta(days=7)
        min_comments = 2

        cleaned_url = cleanurl.cleanurl(url)
        cu = cleaned_url.schemeless_url if cleaned_url else ""
        cleaned_url = cleanurl.cleanurl(
            url,
            generic=True,
            respect_semantics=True,
            host_remap=False,
        )
        url = cleaned_url.schemeless_url if cleaned_url else ""

        ds = (
            cls.objects.filter(schemeless_story_url__iexact=url)
            | cls.objects.filter(schemeless_story_url__iexact=cu)
            | cls.objects.filter(canonical_story_url=cu)
        )

        ds = ds.exclude(schemeless_story_url__isnull=True)
        ds = ds.exclude(schemeless_story_url="")

        if only_relevant_stories:
            ds = ds.filter(
                Q(comment_count__gte=min_comments)
                | Q(created_at__gt=seven_days_ago)
                | Q(_platform="u"),
            )

        ds = ds.annotate(word_similarity=Value(99))

        ds = ds.order_by(
            "_platform",
            "-word_similarity",
            "-created_at",
            "-platform_id",
        )

        return ds, cu, cu

    @classmethod
    def of_url_or_title(cls, url_or_title):
        if not url_or_title:
            return cls.objects.none(), "", ""

        seven_days_ago = timezone.now() - datetime.timedelta(days=7)
        min_comments = 2
        min_score = 2

        if not url_or_title:
            return None, None, None

        u = cleanurl.cleanurl(
            url_or_title,
            generic=True,
            respect_semantics=True,
            host_remap=False,
        )
        url = u.schemeless_url if u else ""
        scheme = u.scheme if u else ""
        u = cleanurl.cleanurl(url_or_title)
        cu = u.schemeless_url if u else ""

        ds = (
            cls.objects.filter(schemeless_story_url__iexact=url)
            | cls.objects.filter(schemeless_story_url__iexact=cu)
            | cls.objects.filter(canonical_story_url=cu)
        )

        ds = ds.exclude(schemeless_story_url__isnull=True)
        ds = ds.exclude(schemeless_story_url="")

        ds = ds.annotate(search_rank=Value(1))

        ds = ds.filter(
            Q(comment_count__gte=min_comments)
            | Q(created_at__gt=seven_days_ago)
            | Q(_platform="u"),
        )

        ts = None

        if scheme not in ("http", "https", "ftp"):
            # xojoc: test search with:
            #   https://discu.eu/q/APL%20in%20JavaScript
            #   https://discu.eu/q/Go%201.4.1%20has%20been%20released
            #   https://discu.eu/q/The%20Gosu%20Programming%20Language
            #   https://discu.eu/q/F-35%20C%2B%2B%20coding%20standard%20%5Bpdf%5D
            #   https://discu.eu/q/The%20Carnap%20Programming%20Language
            #   https://discu.eu/?q=For+C+programmers+that+hate+C%2B%2B+%282011%29

            query = url_or_title
            site_prefix = "site:"
            tokens = url_or_title.split()

            if tokens[0].startswith(site_prefix) and len(tokens[0]) > len(
                site_prefix,
            ):
                query = " ".join(tokens[1:])

                url_prefix = tokens[0][len(site_prefix):].lower()
                curl_prefix = cleanurl.cleanurl(url_prefix, generic=True)

                ts = (
                    cls.objects.filter(schemeless_story_url__iexact=url_prefix)
                    | cls.objects.filter(
                        schemeless_story_url__iexact=url_prefix,
                    )
                    | cls.objects.filter(canonical_story_url=curl_prefix)
                    | cls.objects.filter(
                        schemeless_story_url__istartswith=url_prefix,
                    )
                    | cls.objects.filter(
                        schemeless_story_url__istartswith=curl_prefix,
                    )
                    | cls.objects.filter(
                        canonical_story_url__startswith=url_prefix,
                    )
                    | cls.objects.filter(
                        canonical_story_url__startswith=curl_prefix,
                    )
                )

            if len(query) > 1:
                q = title.normalize(query, stem=False)
                psq = SearchQuery(q, search_type="plain")

                base = cls.objects
                if ts is not None:
                    base = ts

                ts = base.annotate(
                    search_rank=Round(SearchRank("title_vector", psq), 2),
                )
                ts = ts.filter(title_vector=psq)
            elif ts is not None:
                ts = ts.annotate(search_rank=Value(1))

            if ts is not None:
                ts = ts.filter(
                    (
                        Q(comment_count__gte=min_comments)
                        & Q(score__gte=min_score)
                    )
                    | Q(created_at__gt=seven_days_ago)
                    | Q(_platform="u"),
                )
                ts = ts.exclude(schemeless_story_url__isnull=True)
                ts = ts.exclude(schemeless_story_url="")

                ts = ts[:40]

        if ts is not None:
            ds = ds.union(ts)

        ds = ds.order_by("-search_rank", "-created_at", "-platform_id")

        ds = ds[:50]

        return ds, cu, cu

    @classmethod
    def delete_useless_discussions(cls):
        six_months_ago = timezone.now() - datetime.timedelta(days=30 * 6)
        _ = (
            cls.objects.filter(comment_count=0).filter(
                created_at__lte=six_months_ago,
            )
        ).delete()


class StatisticsDecoder(json.JSONDecoder):
    def __init__(self):
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object)

    @classmethod
    def dict_to_object(cls, d):
        for k in d:
            if k.startswith("date__"):
                d[k] = dateutil_parser.parse(d[k])

        return d


class Statistics(models.Model):
    name = models.CharField(primary_key=True, max_length=100)
    statistics = models.JSONField(
        encoder=DjangoJSONEncoder,
        decoder=StatisticsDecoder,
    )

    @override
    def __str__(self):
        return self.name

    @classmethod
    def update_platform_statistics(cls, statistics):
        _ = cls.objects.update_or_create(
            name="platform",
            defaults={"statistics": {"data": statistics}},
        )

    @classmethod
    def update_top_stories_statistics(cls, statistics):
        _ = cls.objects.update_or_create(
            name="top_stories",
            defaults={"statistics": {"data": statistics}},
        )

    @classmethod
    def update_top_domains_statistics(cls, statistics):
        _ = cls.objects.update_or_create(
            name="top_domains",
            defaults={"statistics": {"data": statistics}},
        )

    @classmethod
    def platform_statistics(cls):
        try:
            ps = cls.objects.get(name="platform").statistics["data"]
            for p in ps:
                p["platform"] = Platform(p["platform"])
        except cls.DoesNotExist:
            return []

        return ps

    @classmethod
    def top_stories_statistics(cls):
        try:
            return cls.objects.get(name="top_stories").statistics["data"]
        except cls.DoesNotExist:
            return []

    @classmethod
    def top_domains_statistics(cls):
        try:
            return cls.objects.get(name="top_domains").statistics["data"]
        except cls.DoesNotExist:
            return []

    @classmethod
    def all_statistics(cls):
        return {
            "platform": cls.platform_statistics(),
            "top_stories": cls.top_stories_statistics(),
            "top_domains": cls.top_domains_statistics(),
        }


class Tweet(models.Model):
    tweet_id = models.BigIntegerField(primary_key=True, null=False)
    bot_name = models.CharField(max_length=255)
    bot_names = postgres_fields.ArrayField(
        models.CharField(max_length=255),
        blank=True,
        default=list,
    )

    discussions = models.ManyToManyField(Discussion)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @override
    def __str__(self) -> str:
        return f"{self.bot_names}: {self.tweet_id}"

    @override
    def save(self, *args, **kwargs):
        self.bot_names = self.bot_names or []
        if self.bot_name:
            self.bot_names.append(self.bot_name)

        self.bot_names = sorted(set(self.bot_names))

        super().save(*args, **kwargs)


class MastodonPost(models.Model):
    post_id = models.BigIntegerField(primary_key=True, null=False)
    bot_names = postgres_fields.ArrayField(
        models.CharField(max_length=255),
        blank=True,
        default=list,
    )

    discussions = models.ManyToManyField(Discussion)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @override
    def __str__(self) -> str:
        return f"{self.bot_names}: {self.post_id}"

    @override
    def save(self, *args, **kwargs):
        self.bot_names = sorted(set(self.bot_names or []))

        super().save(*args, **kwargs)


class Resource(models.Model):
    TITLE_MAX_LEN = 2048

    id = models.BigAutoField(primary_key=True)  # noqa: A003

    scheme = models.CharField(max_length=25)

    url = models.CharField(
        max_length=100_000,
        blank=True,
        default=None,
    )

    canonical_url = models.CharField(max_length=100_000, blank=True)

    title = models.CharField(max_length=2048)
    normalized_title = models.CharField(
        max_length=TITLE_MAX_LEN,
        blank=True,
    )

    tags = postgres_fields.ArrayField(
        models.CharField(max_length=255, blank=True),
        blank=True,
    )

    normalized_tags = postgres_fields.ArrayField(
        models.CharField(max_length=255, blank=True),
        blank=True,
    )

    clean_html = models.TextField()

    excerpt = models.TextField()

    last_fetch = models.DateTimeField(null=True)
    last_processed = models.DateTimeField(null=True)

    status_code = models.IntegerField(null=True)

    links = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="Link",
        related_name="inbound_link",
    )
    inbound_link: models.Manager[  # pyright: ignore [reportUninitializedInstanceVariable]
        "Link"
    ]

    pagerank = models.FloatField(default=0, null=False)

    class Meta(TypedModelMeta):
        indexes: Sequence[models.Index] = [
            models.Index(
                name="index_url",
                fields=["url"],
                opclasses=["varchar_pattern_ops"],
            ),
            models.Index(
                name="index_canonical_url",
                fields=["canonical_url"],
                opclasses=["varchar_pattern_ops"],
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"{self.id}"

    @override
    def save(self: Self, *args: Any, **kwargs: Any) -> None:
        self._pre_save()
        super().save(*args, **kwargs)

    def _pre_save(self):
        self.tags = self.tags or []
        self.title = self.title or ""

        self.title = self.title.replace("\x00", "")
        self.title = self.title[: self.TITLE_MAX_LEN]

        if self.url:
            u = cleanurl.cleanurl("//" + self.url)
            if u:
                self.canonical_url = u.schemeless_url
            else:
                self.canonical_url = None

        if not self.canonical_url:
            self.canonical_url = self.url

        self.normalized_title = title.normalize(
            self.title,
            None,
            (self.story_url or ""),
            self.tags,
            stem=False,
        )

        self.normalized_tags = (
            tags.normalize(
                self.tags,
                None,
                self.title,
                (self.story_url or ""),
            )
            or []
        )

        self.clean_html = self.clean_html or ""

    @property
    def complete_url(self):
        return self.scheme + "://" + self.url

    @classmethod
    def by_url(cls, url):
        if not url:
            return None

        cu = cleanurl.cleanurl(url)
        su = cleanurl.cleanurl(
            url,
            generic=True,
            respect_semantics=True,
            host_remap=False,
        )

        if not cu or not su:
            return None

        return (
            cls.objects.filter(url=su.schemeless_url)
            | cls.objects.filter(url=cu.schemeless_url)
            | cls.objects.filter(canonical_url=cu.schemeless_url)
        ).first()

    def outbound_resources(self):
        ols = self.links.all().distinct()
        ols = ols.annotate(
            discussions_comment_count=Coalesce(
                Subquery(
                    Discussion.objects.filter(
                        canonical_story_url=OuterRef("canonical_url"),
                    )
                    .values("canonical_story_url")
                    .annotate(comment_count=Sum("comment_count"))
                    .values("comment_count"),
                ),
                Value(0),
            ),
        )

        return ols.order_by("-discussions_comment_count")

    def inbound_resources(self):
        ils = self.inbound_link.all().distinct()
        ils = ils.annotate(
            discussions_comment_count=Coalesce(
                Subquery(
                    Discussion.objects.filter(
                        canonical_story_url=OuterRef("canonical_url"),
                    )
                    .values("canonical_story_url")
                    .annotate(comment_count=Sum("comment_count"))
                    .values("comment_count"),
                ),
                Value(0),
            ),
        )
        #         Discussion.objects
        #         .filter(canonical_story_url=OuterRef('canonical_url'))
        #         .values('canonical_story_url')
        #         .annotate(unnest_tags=Subquery(
        #             Discussion.objects
        #   .filter(canonical_story_url=OuterRef('canonical_story_url'))
        #             .annotate(normalized_tag=Func(F('normalized_tags'),
        #                                           function='unnest'))))
        #         .aggregate(normalized_tags=ArrayAgg('unnest_tags')
        #         Discussion.objects
        #         .filter(canonical_story_url=OuterRef('canonical_url'))
        #         .values('canonical_story_url')
        #         .annotate(normalized_tag=Func(F('normalized_tags'),
        #                                       function='unnest'))
        #         .annotate(normalized_tags=ArrayAgg('normalized_tag'))
        #         .values('normalized_tags')))

        #     Discussion.objects
        #     .filter(canonical_story_url=OuterRef('canonical_url'))
        #     .values('canonical_story_url')
        #     .annotate(normalized_tags=Func(F('normalized_tags'),
        #                                    function='unnest'))
        #     .values_list('normalized_tags', flat=True))))

        return ils.order_by("-discussions_comment_count")

    @property
    def story_url(self):
        if not self.scheme or not self.url:
            return None

        return f"{self.scheme}://{self.url}"

    @property
    def author(self):
        # TODO: for now extract at runtime. In the future add to the model
        author = extract.Author()
        if self.clean_html:
            s = extract.structure(self.clean_html, self.story_url)
            if s and s.author:
                author = s.author

        if not author.twitter_account:
            with contextlib.suppress(Exception):
                author.twitter_account = extract.get_github_user_twitter(
                    self.story_url,
                )

        return author


class Link(models.Model):
    from_resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="from_resource",
    )
    to_resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="to_resource",
    )

    anchor_title = models.TextField()
    anchor_text = models.TextField()
    anchor_rel = models.TextField()

    @override
    def __str__(self) -> str:
        return f"{self.from_resource.id} -> {self.to_resource.id}"

    @override
    def save(self, *args: Any, **kwargs: Any) -> None:
        self.anchor_title = self.anchor_title or ""
        self.anchor_text = self.anchor_text or ""
        self.anchor_rel = self.anchor_rel or ""
        super().save(*args, **kwargs)


# class HackerNewsItem(models.Model):
#     class Type(models.TextChoices):


class APIClient(models.Model):
    name = models.TextField()
    token = models.TextField(blank=True)
    limited = models.BooleanField(default=False)
    email = models.TextField(blank=True)
    url = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    @override
    def __str__(self) -> str:
        return f"{self.name} - {self.email}"

    @override
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        super().save(*args, **kwargs)

    @classmethod
    def generate_token(cls):
        return secrets.token_urlsafe(32)

    def get_statistics(self, endpoint=None):
        return api_statistics.get("api-v0", self.token, endpoint)


class Subscriber(models.Model):
    suspected_spam = models.BooleanField(default=False)
    email = models.EmailField()
    topic = models.CharField(max_length=255, choices=topics.topics_choices)
    verification_code = models.CharField(max_length=15)
    confirmed = models.BooleanField(default=False)
    subscribed_from = models.CharField(
        max_length=2,
        blank=True,
        choices=[("wf", "Web Form"), ("em", "Email Comand")],
    )
    entry_created_at = models.DateTimeField(auto_now_add=True)
    entry_updated_at = models.DateTimeField(auto_now=True)

    unsubscribed_from = models.CharField(
        max_length=3,
        blank=True,
        choices=[("wf", "Web Form"), ("em", "Email Comand"), ("aws", "AWS")],
    )
    unsubscribed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    http_headers = models.JSONField(null=True)

    aws_notification = models.JSONField(null=True)

    weeks_clicked = postgres_fields.ArrayField(
        models.CharField(max_length=6),
        null=True,
    )

    unsubscribed_feedback = models.TextField(
        blank=True,
        verbose_name="Unsubscription reason",
        help_text="Let us know how to improve.",
    )

    class Meta(TypedModelMeta):
        constraints: Sequence[models.BaseConstraint] = [
            models.UniqueConstraint(
                fields=["email", "topic"],
                name="unique_email_topic",
            ),
        ]

    @override
    def __str__(self) -> str:
        return (
            f"{self.email} {self.topic} ({self.confirmed} confirmed, "
            f"{self.unsubscribed} unsubscribed)"
        )

    @override
    def save(self, *args, **kwargs):
        if not self.verification_code:
            self.verification_code = self.generate_verification_code()

        if self.weeks_clicked:
            self.weeks_clicked = sorted(self.weeks_clicked, reverse=True)

        super().save(*args, **kwargs)

    @classmethod
    def mailing_list(cls, topic):
        q = cls.objects.filter(confirmed=True).filter(unsubscribed=False)

        if topic:
            q = q.filter(topic=topic)

        return q

    @classmethod
    def generate_verification_code(cls):
        import secrets

        return secrets.token_urlsafe(5)

    def send_confirmation_email(self):
        confirmation_url = (
            f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}/weekly/confirm_email?"
            + urllib.parse.urlencode(
                [
                    ("topic", self.topic),
                    ("email", self.email),
                    ("verification_code", self.verification_code),
                ],
            )
        )
        email_util.send(
            (
                f"Confirm subscription to Weekly "
                f"{topics.topics[self.topic]['name']} newsletter"
            ),
            template_loader.render_to_string(
                "web/weekly_subscribe_confirm.txt",
                {
                    "ctx": {
                        "topic": topics.topics[self.topic],
                        "confirmation_url": confirmation_url,
                    },
                },
            ),
            topics.topics[self.topic]["from_email"],
            self.email,
        )

    def send_subscription_confirmation_email(self):
        email_util.send(
            (
                f"Subscribed to Weekly {topics.topics[self.topic]['name']} "
                "newsletter"
            ),
            template_loader.render_to_string(
                "web/weekly_subscribe_confirmation.txt",
                {
                    "ctx": {
                        "topic": topics.topics[self.topic],
                    },
                },
            ),
            topics.topics[self.topic]["from_email"],
            self.email,
        )

    def unsubscribe_url(self):
        return (
            f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}/weekly/confirm_unsubscription?"
            + urllib.parse.urlencode(
                [
                    ("topic", self.topic),
                    ("email", self.email),
                    ("verification_code", self.verification_code),
                ],
            )
        )

    def unsubscribe(self):
        self.unsubscribed = True
        self.unsubscribed_at = timezone.now()

    def subscribe(self):
        self.confirmed = True
        self.unsubscribed = False

    def send_unsubscribe_confirmation_email(self):
        email_util.send(
            (
                f"Unsubscribed from Weekly {topics.topics[self.topic]['name']}"
                " newsletter"
            ),
            template_loader.render_to_string(
                "web/weekly_unsubscribe_confirmation.txt",
                {
                    "ctx": {
                        "topic": topics.topics[self.topic],
                    },
                },
            ),
            topics.topics[self.topic]["from_email"],
            self.email,
        )

    def clicked(self, year, week):
        self.weeks_clicked = (self.weeks_clicked or []) + [f"{year}{week}"]


class CustomUser(AbstractUser):
    premium_active = models.BooleanField(default=False)
    premium_active_from = models.DateTimeField(blank=True, null=True)
    premium_cancelled = models.BooleanField(default=False)
    premium_cancelled_on = models.DateTimeField(blank=True, null=True)

    complete_name = models.TextField(
        blank=True,
        verbose_name="Preferred name",
        help_text="How would you like to be called?",
    )

    generic_ads = models.BooleanField(
        default=False,
        help_text="Show generic ads even if subscribed to premium",
    )
    job_ads = models.BooleanField(
        default=False,
        help_text="Show job ads even if subscribed to premium",
    )

    api = models.OneToOneField(APIClient, on_delete=models.SET_NULL, null=True)

    stripe_customer_id = models.TextField(blank=True)

    rss_id = models.TextField()
    emailaddress_set: models.Manager[  # pyright: ignore [reportUninitializedInstanceVariable]
        "allauth_models.EmailAddress"
    ]

    @override
    def __str__(self):
        return self.email

    @override
    def save(self, *args, **kwargs):
        if not self.api:
            self.api = APIClient.objects.create(name=f"User {self.pk}")
        if not self.rss_id:
            self.rss_id = secrets.token_urlsafe(5)

        super().save(*args, **kwargs)

    def trial_length_days(self):
        _ = self
        return 14

    def trial_remaining_days(self):
        return max(
            0,
            self.trial_length_days()
            - (timezone.now() - self.date_joined).days,
        )

    @property
    def is_premium(self):
        return self.premium_active and not self.premium_cancelled

    @property
    def email_verified(self):
        return (
            self.emailaddress_set.filter(primary=True)
            .filter(verified=True)
            .exists()
        )

    def max_mention_rules(self):
        if self.is_premium:
            return 20
        return 2

    def notifications_sent(self, last_minutes=15):
        t = timezone.now() - datetime.timedelta(minutes=last_minutes)
        ns = (
            MentionNotification.objects.filter(mention__user__pk=self.pk)
            .filter(email_sent=True)
            .filter(email_sent_at__gte=t)
        )
        return ns.count()


class AD(models.Model):
    topics = _CustomArrayField(
        models.CharField(
            max_length=255,
            choices=topics.topics_choices,
        ),
        choices=topics.topics_choices,
        help_text=(
            "Ads are always reviewed manually and only ads "
            "relevant to the selected topics are approved"
        ),
    )
    week_year = models.IntegerField(null=True, blank=True)
    week_week = models.IntegerField(null=True, blank=True)

    consecutive_weeks = models.PositiveIntegerField(
        default=1,
        help_text="How many weeks in a row would you like to run the ad?",
    )

    newsletter = models.BooleanField(
        default=True,
        help_text="""Would you like to advertise in the <a href="/weekly/" title="Weekly newsletters">newsletters</a>?<br/>
If you select multiple topics, duplicate emails are counted only once.
        """,
    )
    twitter = models.BooleanField(
        default=False,
        help_text=(
            'Would you like to advertise on <a href="/social#twitter" '
            'title="Twitter bots">Twitter</a>?'
        ),
    )
    mastodon = models.BooleanField(
        default=False,
        help_text=(
            'Would you like to advertise on <a href="/social#mastodon" '
            'title="Mastodon bots">Mastodon</a>?'
        ),
    )

    floss_project = models.BooleanField(
        default=False,
        verbose_name="FLOSS project",
        help_text="FLOSS projects get a 20% discount",
    )
    floss_repository = models.TextField(
        blank=True,
        help_text="FLOSS projects get a 20% discount",
    )

    title = models.TextField(blank=True)
    body = models.TextField(
        verbose_name="Ad message",
        help_text="""Only <strong>plain text</strong> is accepted for now.
        If you selected Twitter above please take in consideration character limits.""",
    )
    url = models.TextField(verbose_name="Ad URL", blank=True)

    comments = models.TextField(
        blank=True,
        help_text="""Comments for the ad approver.<br/>
If you have preferences for when to tweet or toot or anything else let us know here.""",
    )

    estimated_total_euro = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )

    estimated_newsletter_subscribers = models.IntegerField(
        null=True,
        blank=True,
    )
    estimated_twitter_followers = models.IntegerField(null=True, blank=True)
    estimated_mastodon_followers = models.IntegerField(null=True, blank=True)

    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)

    approved = models.BooleanField(default=False)

    entry_created_at = models.DateTimeField(auto_now_add=True)
    entry_updated_at = models.DateTimeField(auto_now=True)

    @override
    def __str__(self) -> str:
        return f"{self.pk}"

    @override
    def save(self, *args, **kwargs):
        if self.consecutive_weeks <= 0:
            self.consecutive_weeks = 1
        e = self.estimate()
        self.estimated_total_euro = e["total_euro"]
        self.estimated_newsletter_subscribers = e["newsletter_subscribers"]
        self.estimated_twitter_followers = e["twitter_followers"]
        self.estimated_mastodon_followers = e["mastodon_followers"]

        super().save(*args, **kwargs)

    def estimate(self):
        total_euro = 0
        newsletter_subscribers = 0
        twitter_followers = 0
        mastodon_followers = 0

        if self.newsletter:
            subscribers = Subscriber.mailing_list(None).distinct("email")
            subscribers = subscribers.filter(topic__in=self.topics)
            newsletter_subscribers = subscribers.count()

            total_euro += newsletter_subscribers * 15 / 1000

        if self.twitter:
            twitter_followers = 0
            for topic in self.topics:
                username = topics.topics[topic]["twitter"]["account"]
                if username:
                    twitter_followers += twitter_api.get_followers_count(
                        [username],
                    )[username]
            total_euro += twitter_followers * 5 / 1000

        if self.mastodon:
            mastodon_followers = 0
            for topic in self.topics:
                username = topics.topics[topic]["mastodon"]["account"].split(
                    "@",
                )[1]
                if username:
                    mastodon_followers += mastodon_api.get_followers_count(
                        [username],
                    )[username]

            total_euro += mastodon_followers * 5 / 1000

        if self.floss_project or self.floss_repository:
            total_euro *= 0.80

        total_euro *= self.consecutive_weeks

        total_euro = round(total_euro, 2)

        return {
            "total_euro": total_euro,
            "newsletter_subscribers": newsletter_subscribers,
            "twitter_followers": twitter_followers,
            "mastodon_followers": mastodon_followers,
        }


class Mention(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    rule_name = models.CharField(max_length=255, blank=True)

    base_url = models.TextField(
        blank=True,
        verbose_name="URL prefix",
        help_text="""
The discussed URL must have this prefix.</br>
It could be your website, your twitter profile, github profile, etc.<br/>
For example: xojoc.pw, twitter.com/XojocXojoc, github.com/xojoc<br/>

Common subdomains are ignored. So <i>example.com</i> matches <i>www.example.com</i>, <i>m.example.com</i>, <i>example.com</i>, etc.<br/>
If you have different subdomains (like blog. forum. docs. etc.) you have to create a separate rule for them.
    """,
    )

    keyword = models.TextField(
        blank=True,
        help_text="""
The title of the <i>posted</i> story must have this keyword. It could be your brand, name or a product you are interested in.
    """,
    )

    keywords = postgres_fields.ArrayField(
        models.TextField(blank=True),
        blank=True,
        null=True,
        help_text="""
Coma separated list of keywords. The title of the <i>posted</i> story must contain <i>one</i> of these keywords. It could be your brand, your name or a product you are interested in.<br/>
Both the keyword and title of the thread are normalized. So the keywords <i>XOJOC,anotherkeyword</i> will match for example <i>Xojoc's new project</i>, etc.
<br/>
No more than 3 keywords are allowed.
        """,
    )

    platforms = postgres_fields.ArrayField(
        models.CharField(max_length=1, blank=True),
        blank=True,
        help_text="""
Platforms you are interested in. Leave empty to select all.
        """,
    )

    exclude_platforms = postgres_fields.ArrayField(
        models.CharField(max_length=1, blank=True, choices=Platform.choices),
        blank=True,
        null=True,
        help_text="""
Platforms you are NOT interested in.
        """,
    )

    subreddits_exclude = postgres_fields.ArrayField(
        models.CharField(max_length=255, blank=True),
        null=True,
        blank=True,
        verbose_name="Exclude subreddits",
        help_text="""
Coma separated list of subreddits to ignore.
        """,
    )

    min_comments = models.PositiveIntegerField(default=0)
    min_score = models.IntegerField(default=0)

    disabled = models.BooleanField(default=False, verbose_name="Disable")

    entry_created_at = models.DateTimeField(auto_now_add=True)
    entry_updated_at = models.DateTimeField(auto_now=True)

    mentionnotification_set: models.Manager[  # pyright: ignore [reportUninitializedInstanceVariable]
        "MentionNotification"
    ]

    @override
    def __str__(self):
        if self.rule_name:
            return self.rule_name
        if self.base_url and self.keywords:
            return f"{self.base_url} - {self.keywords}"
        if self.base_url:
            return self.base_url
        if self.keywords:
            return ", ".join(self.keywords)
        return str(self.pk)

    @override
    def save(self, *args, **kwargs):
        self.platforms = self.platforms or []

        self.exclude_platforms = self.exclude_platforms or []
        self.exclude_platforms = sorted(self.exclude_platforms)

        self.subreddits_exclude = self.subreddits_exclude or []
        self.subreddits_exclude = [
            s.strip().lower() for s in self.subreddits_exclude
        ]
        self.subreddits_exclude = [s for s in self.subreddits_exclude if s]
        self.subreddits_exclude = sorted(self.subreddits_exclude)

        if self.keyword and not self.keywords:
            self.keywords = [self.keyword]

        self.keywords = self.keywords or []
        self.keywords = [s.strip().lower() for s in self.keywords]
        self.keywords = [s for s in self.keywords if s]
        self.keywords = sorted(self.keywords)

        super().save(*args, **kwargs)

    def notifications_count(self, *, sent_only=False):
        qs = self.mentionnotification_set.all()
        if sent_only:
            qs = qs.filter(sent=True)

        return qs.count()


class MentionNotification(models.Model):
    mention = models.ForeignKey(Mention, on_delete=models.CASCADE)
    discussion = models.ForeignKey(
        Discussion,
        on_delete=models.SET_NULL,
        null=True,
    )

    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(blank=True, null=True)

    entry_created_at = models.DateTimeField(auto_now_add=True)
    entry_updated_at = models.DateTimeField(auto_now=True)

    @override
    def __str__(self) -> str:
        return (
            f"Mention: {self.mention.rule_name} "
            f"Discussion: {self.discussion.platform_id}"
        )


class DataBag(models.Model):
    """Store results of expensive computations."""

    key = models.CharField(primary_key=True, blank=False)
    value_json = models.JSONField()

    entry_created_at = models.DateTimeField(auto_now_add=True)
    entry_updated_at = models.DateTimeField(auto_now=True)

    @override
    def __str__(self) -> str:
        return f"{self.key}: {self.value}"

    @property
    def value(self) -> object | None:
        if not self.value_json:
            return None
        return json.loads(self.value_json)

    @value.setter
    def value(self, v):
        self.value_json = DjangoJSONEncoder().encode(v)
