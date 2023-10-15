# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import itertools
import logging
import random
import re
import time
from collections import defaultdict
from email.message import Message

import django.template.loader as template_loader
import sentry_sdk
from celery import shared_task
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, TruncDay
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware

from discussions import settings

from . import (
    category,
    celery_util,
    mastodon,
    models,
    tags,
    topics,
    twitter,
    util,
)

logger = logging.getLogger(__name__)


def base_query(topic):
    qs = (
        models.Discussion.objects.exclude(
            canonical_story_url__startswith="discu.eu/weekly",
        ).exclude(created_at__isnull=True)
        # .filter(comment_count__gte=1)
        .filter(score__gte=2)
    )
    tags = topics.topics[topic].get("tags")
    if tags:
        qs = qs.filter(normalized_tags__overlap=list(tags))
    if topics.topics[topic].get("platform"):
        qs = qs.filter(_platform=topics.topics[topic].get("platform"))
    else:
        qs = (
            qs.exclude(schemeless_story_url__isnull=True)
            .exclude(schemeless_story_url="")
            .exclude(scheme_of_story_url__isnull=True)
            .exclude(scheme_of_story_url="")
        )

    return qs


def week_start(year, week=None):
    if not week:
        year, week = year

    d = datetime.date.fromisocalendar(year, week, 1)
    d = datetime.datetime.combine(d, datetime.time(0, 0))
    return make_aware(d)


def week_end(year, week=None):
    if not week:
        year, week = year

    d = week_start(year, week) + datetime.timedelta(days=7)
    d = datetime.datetime.combine(d, datetime.time(0, 0))
    return make_aware(d)


def all_yearweeks(topic):
    yearweeks = set()
    stories = (
        base_query(topic)
        .annotate(created_at_date=TruncDay("created_at"))
        .values("created_at_date")
        .distinct()
        .order_by()
    )
    for s in stories.iterator():
        ic = s["created_at_date"].isocalendar()
        yearweeks.add((ic.year, ic.week))

    return sorted(yearweeks, reverse=True)


def last_nth_yearweeks(topic, n):
    del topic

    yearweeks = set()
    d = timezone.now()
    for _ in range(n):
        d -= datetime.timedelta(days=7)
        ic = d.isocalendar()
        yearweeks.add((ic.year, ic.week))

    return sorted(yearweeks, reverse=True)[:n]


def __get_random_old_stories(topic, categories):
    found_categories = defaultdict(list)
    time_ago = timezone.now() - datetime.timedelta(days=365)

    for cat, cat_count in categories.items():
        stories = (
            base_query(topic)
            .filter(created_at__lt=time_ago)
            .filter(comment_count__gte=100)
            .filter(score__gte=100)
            .filter(category=cat)
        )

        # if util.is_dev():

        count = stories.count()
        if count < cat_count * 2:
            continue

        for _ in range(cat_count * 2):
            if len(found_categories[cat]) >= categories.get(cat, 0):
                break
            j = random.randint(0, count - 1)  # noqa: S311
            rs = stories[j]
            if rs in found_categories[cat]:
                continue

            discussions, _, _ = models.Discussion.of_url(
                rs.story_url,
                only_relevant_stories=True,
            )
            discussion_counts = (
                discussions.aggregate(
                    total_comments=Coalesce(Sum("comment_count"), 0),
                    total_discussions=Coalesce(Count("platform_id"), 0),
                )
                or {}
            )
            rs.__dict__["total_comments"] = discussion_counts.get(
                "total_comments",
            )
            rs.__dict__["total_discussions"] = discussion_counts.get(
                "total_discussions",
            )
            found_categories[cat].append(rs)

    return found_categories


def __get_stories(topic, year, week):
    ws = week_start(year, week)
    we = week_end(year, week)

    stories = (
        base_query(topic)
        .filter(created_at__gte=ws)
        .filter(created_at__lt=we)
        # .distinct("canonical_story_url")
        # .order_by("comment_count")
        # .order_by("created_at")
    )

    min_comments = 2
    min_score = 1

    stories = stories.annotate(
        total_comments=Coalesce(
            Subquery(
                models.Discussion.objects.filter(
                    canonical_story_url=OuterRef("canonical_story_url"),
                )
                .filter(score__gte=min_score)
                .filter(comment_count__gte=min_comments)
                .values("canonical_story_url")
                .annotate(total_comments=Sum("comment_count"))
                .values("total_comments"),
            ),
            Value(0),
        ),
    )

    stories = stories.annotate(
        total_discussions=Coalesce(
            Subquery(
                models.Discussion.objects.filter(
                    canonical_story_url=OuterRef("canonical_story_url"),
                )
                .filter(score__gte=min_score)
                .filter(comment_count__gte=min_comments)
                .values("canonical_story_url")
                .annotate(total_discussions=Count("platform_id"))
                .values("total_discussions"),
            ),
            Value(0),
        ),
    )

    stories = stories.filter(total_discussions__lt=20)

    if util.is_dev():
        logger.debug(
            "weekly: %s %s %s: stories count %s",
            topic,
            ws,
            we,
            stories.count(),
        )

    unique_stories = []
    unique_urls = set()

    for story in stories:
        if (
            story.canonical_story_url
            and story.canonical_story_url in unique_urls
        ):
            logger.debug(
                "weekly: duplicate: %s - %s %s",
                story.platform_id,
                story.canonical_story_url,
                story.title,
            )
            continue

        story.category = category.derive(story)

        unique_stories.append(story)

        if story.canonical_story_url:
            unique_urls.add(story.canonical_story_url)

    return unique_stories


def _get_digest(topic, year, week):
    platform = topics.topics[topic].get("platform")
    stories = __get_stories(topic, year, week)
    stories = sorted(stories, key=lambda x: x.category)
    digest = [
        (cat, category.name(cat, platform), list(stories))
        for cat, stories in itertools.groupby(stories, lambda x: x.category)
    ]

    digest = sorted(digest, key=lambda x: category.categories[x[0]]["sort"])

    for cat, _, stories in digest:
        if topic == "hackernews":
            stories.sort(key=lambda x: x.comment_count, reverse=True)
        else:
            stories.sort(key=lambda x: x.total_comments, reverse=True)

        if cat == "article":
            stories[:] = stories[:15]
        elif cat == "project":
            stories[:] = stories[:10]
        elif cat == "askplatform":
            stories[:] = stories[:3]
        elif cat == "tellplatform":
            stories[:] = stories[:2]
        elif cat == "release":
            stories[:] = stories[:10]
        elif cat == "video":
            stories[:] = stories[:7]
    return digest


def __get_digest_old_stories(topic, year=None, week=None):
    del topic
    del year
    del week
    return {}
    # if topics.topics[topic].get("platform"):


def __generate_breadcrumbs(topic=None, year=None, week=None):
    breadcrumbs = []
    breadcrumbs.extend(
        (
            {"name": "Home", "title": "Discu.eu", "url": "/"},
            {
                "name": "Weekly newsletter",
                "title": "Weekly newsletter",
                "url": reverse("web:weekly_index"),
            },
        ),
    )
    if topic:
        breadcrumbs.append(
            {
                "name": topics.topics[topic]["name"],
                "title": f"{topics.topics[topic]['name']} Weekly",
                "url": reverse("web:weekly_topic", args=[topic]),
            },
        )
    if topic and year and week:
        name = topics.topics[topic]["name"]
        breadcrumbs.append(
            {
                "name": f"Week {week}/{year}",
                "title": f"{name} recap for week {week}/{year}",
                "url": reverse(
                    "web:weekly_topic_week",
                    args=[topic, year, week],
                ),
            },
        )

    for breadcrumb in breadcrumbs:
        if breadcrumb.get("url"):
            breadcrumb[
                "url"
            ] = f'{settings.APP_SCHEME}://{settings.APP_DOMAIN}{breadcrumb["url"]}'

    return breadcrumbs


def index_context():
    ctx = {}
    ctx["topics"] = {
        k: v for k, v in topics.topics.items() if k not in ["laarc"]
    }
    ctx["breadcrumbs"] = __generate_breadcrumbs()
    return ctx


def topic_context(topic):
    ctx = {}
    ctx["topic_key"] = topic
    ctx["topic"] = topics.topics.get(topic)
    if not ctx["topic"]:
        return None
    ctx["yearweeks"] = []
    yearweeks = last_nth_yearweeks(topic, 3)
    for yearweek in yearweeks:
        ctx["yearweeks"].append(
            {
                "year": yearweek[0],
                "week": yearweek[1],
                "week_start": week_start(yearweek),
                "week_end": week_end(yearweek) - datetime.timedelta(days=1),
            },
        )
    ctx["breadcrumbs"] = __generate_breadcrumbs(topic)

    twitter = topics.topics[topic].get("twitter")
    if twitter.get("account"):
        ctx["twitter_account"] = "@" + twitter.get("account")
    mastodon_cfg = topics.topics[topic].get("mastodon")
    if mastodon_cfg.get("account"):
        ctx["mastodon_account"] = (
            "@" + mastodon_cfg.get("account").split("@")[1]
        )
        ctx["mastodon_account_url"] = mastodon.profile_url(
            mastodon_cfg.get("account"),
        )

    return ctx


def topic_week_context(topic: str, year: int, week: int) -> dict | None:
    ctx = {}
    ctx["topic_key"] = topic
    ctx["topic"] = topics.topics.get(topic)
    if not ctx["topic"]:
        return None
    ctx["year"] = year
    ctx["week"] = week
    try:
        ctx["week_start"] = week_start(year, week)
        ctx["week_end"] = week_end(year, week) - datetime.timedelta(minutes=1)
    except ValueError:
        return None
    ctx["digest"] = _get_digest(topic, year, week)
    ctx["digest_old_stories"] = __get_digest_old_stories(
        topic,
        year=None,
        week=None,
    )
    ctx["breadcrumbs"] = __generate_breadcrumbs(topic, year, week)
    ctx[
        "web_link"
    ] = f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}" + reverse(
        "web:weekly_topic_week",
        args=[topic, year, week],
    )
    twitter = topics.topics[topic].get("twitter")
    if twitter.get("account"):
        ctx["twitter_account"] = "@" + twitter.get("account")
    mastodon_cfg = topics.topics[topic].get("mastodon")
    if mastodon_cfg.get("account"):
        ctx["mastodon_account"] = (
            "@" + mastodon_cfg.get("account").split("@")[1]
        )
        ctx["mastodon_account_url"] = mastodon.profile_url(
            mastodon_cfg.get("account"),
        )
    return ctx


def topic_week_context_cached(topic, year, week):
    ic = timezone.now().isocalendar()
    pic = (timezone.now() - datetime.timedelta(days=7)).isocalendar()
    cw = (ic.year, ic.week)
    cache_timeout = 0

    if (year, week) >= cw:
        cache_timeout = 15 * 60
    elif (year, week) == (pic.year, pic.week) and ic.weekday == 1:
        cache_timeout = 24 * 60 * 60
    else:
        cache_timeout = 10 * 7 * 24 * 60 * 60  # 10 weeks

    if util.is_dev():
        cache_timeout = 0

    key = f"weekly:{topic}:{year}:{week}"
    ctx = cache.get(key)

    if ctx:
        return ctx

    ctx = topic_week_context(topic, year, week)
    if ctx and cache_timeout:
        cache.set(key, ctx, cache_timeout)

    return ctx


def imap_handler(
    message: Message,
    message_id: str,
    from_email: tuple[str, str],
    to_email: str,
    subject: str,
    body: str,
) -> bool:
    _ = message
    logger.debug(
        f"""
    Message_id: {message_id}
    From: {from_email}
    To: {to_email}
    Subject: {subject}
    ---
    {body}
    """,
    )

    matches = re.search(r"weekly_([a-z0-9]+)@discu\.eu", to_email)
    if not matches:
        return False
    topic_key = matches[1]

    topic = topics.topics.get(topic_key)
    if not topic:
        return False

    if settings.EMAIL_TO_PREFIX and not to_email.startswith(
        settings.EMAIL_TO_PREFIX,
    ):
        logger.debug(f"Weekly email NOT dev: '{topic_key}' '{from_email}'")
        return False

    tokens = body.lower().strip().split()
    if len(tokens) > 0 and tokens[0] == "subscribe":
        try:
            subscriber = models.Subscriber.objects.get(
                topic=topic_key,
                email=from_email,
            )
            if subscriber.confirmed and not subscriber.unsubscribed:
                subscriber = None
                logger.info(
                    f"Subsription exists for {from_email} topic {topic_key}",
                )
            else:
                subscriber.subscribe()
                subscriber.save()
        except models.Subscriber.DoesNotExist:
            subscriber = models.Subscriber(email=from_email, topic=topic_key)
            subscriber.subscribe()
            subscriber.save()

        if subscriber:
            subscriber.send_subscription_confirmation_email()
            logger.info(
                f"Confirmation email sent to {from_email} topic {topic_key}",
            )
            return True

    if len(tokens) > 0 and tokens[0] == "unsubscribe":
        try:
            subscriber = models.Subscriber.objects.get(
                topic=topic_key,
                email=from_email,
            )
        except models.Subscriber.DoesNotExist:
            logger.info(
                f"No subscription found for '{topic_key}' '{from_email}'",
            )
            subscriber = None

        if subscriber:
            subscriber.unsubscribe()
            subscriber.save()
            subscriber.send_unsubscribe_confirmation_email()
            logger.info(
                f"Unsubscribtion email sent to {from_email} topic {topic_key}",
            )
            return True

    return False


def __rewrite_urls(ctx, subscriber, topic, year, week):
    for _, _, stories in ctx.get("digest"):
        for story in stories:
            if story.story_url:
                story.__dict__["click_story_url"] = util.click_url(
                    story.story_url,
                    subscriber,
                    topic,
                    year,
                    week,
                )
                story.__dict__["click_discussions_url"] = util.click_url(
                    util.discussions_url(story.story_url),
                    subscriber,
                    topic,
                    year,
                    week,
                )
            else:
                story.__dict__["click_discussions_url"] = util.click_url(
                    story.discussion_url,
                    subscriber,
                    topic,
                    year,
                    week,
                )


def send_mass_email(topic, year, week, *, testing=True, only_subscribers=None):
    if only_subscribers is None:
        only_subscribers = []
    if only_subscribers:
        subscribers = only_subscribers
    else:
        subscribers = list(models.Subscriber.mailing_list(topic))

    random.shuffle(subscribers)

    logger.info(
        f"weekly: sending mail to {len(subscribers)} subscribers for {topic} {week}/{year}",
    )
    ctx = topic_week_context(topic, year, week)

    if not ctx or not ctx.get("digest"):
        logger.warning(f"weekly: no articles {topic} {week}/{year}")
        return

    messages = []

    subject = f"{topics.topics[topic]['name']} recap for week {week}/{year}"
    if util.is_dev():
        subject = "[DEV] " + subject

    from_email = topics.topics[topic].get("from_email")
    if not from_email:
        logger.error(f"weekly: {topic} missing from_email")
        return

    for subscriber in subscribers:
        ctx["subscriber"] = subscriber

        __rewrite_urls(ctx, subscriber, topic, year, week)

        text_content = template_loader.render_to_string(
            "web/weekly_topic_digest.txt",
            {"ctx": ctx},
        )

        html_content = template_loader.render_to_string(
            "web/weekly_topic_week_email.html",
            {"ctx": ctx},
        )

        msg = EmailMultiAlternatives(
            subject,
            text_content,
            from_email,
            [subscriber.email],
        )
        msg.attach_alternative(html_content, "text/html")

        messages.append(msg)

    if testing:
        logger.info(messages)
        return

    if not messages:
        return

    connection = mail.get_connection()
    messages_it = iter(messages)
    # current SES limit rate
    limit_rate = 14 - 1
    while batch := list(itertools.islice(messages_it, limit_rate)):
        try:
            connection.send_messages(batch)
            time.sleep(1)
        except BaseException:
            logger.exception("send_messages: % %", topic, len(batch))
            _ = sentry_sdk.capture_exception()
            time.sleep(10)


@shared_task(bind=True, ignore_result=False)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_send_weekly_email(self):
    _ = self
    six_days_ago = timezone.now() - datetime.timedelta(days=6)
    year = six_days_ago.isocalendar().year
    week = six_days_ago.isocalendar().week

    for topic in topics.topics:
        send_mass_email(topic, year, week, testing=False)


@shared_task(bind=True, ignore_result=True)
def share_weekly_issue(self):
    _ = self
    d = timezone.now() - datetime.timedelta(days=7)
    ic = d.isocalendar()
    year, week = ic.year, ic.week

    for topic_key, topic in topics.topics.items():
        ctx = topic_week_context(topic_key, year, week)
        if not ctx:
            continue

        if not ctx.get("digest"):
            logger.warning(
                f"weekly share issue: no articles {topic_key} {week}/{year}",
            )
            continue

        issue_url = f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}" + reverse(
            "web:weekly_topic_week",
            args=[topic_key, year, week],
        )

        htags = tags.normalize(topic["tags"])

        status = f"""{topic['name']} recap for week {week}/{year}

{issue_url}
"""

        twitter_status = status
        mastodon_status = status

        if htags:
            twitter_status += f"\n{' '.join(twitter.build_hashtags(htags))}"
            mastodon_status += f"\n{' '.join(mastodon.build_hashtags(htags))}"

        after_status = "\n\nGet RSS feeds and support this bot with the premium plan: https://discu.eu/premium"

        twitter_status += after_status
        mastodon_status += after_status

        if topic.get("twitter"):
            try:
                _ = twitter.tweet(
                    twitter_status,
                    topic.get("twitter").get("account"),
                )
            except Exception:
                logger.exception("weekly share")

        if topic.get("mastodon"):
            try:
                _ = mastodon.post(
                    mastodon_status,
                    topic.get("mastodon").get("account"),
                )
            except Exception:
                logger.exception("weekly share")

        if not util.is_dev():
            time.sleep(random.randint(50, 80))  # noqa: S311


def open_rate(topic):
    last_n = 1
    yearweeks = last_nth_yearweeks(topic, last_n + 1)[1:]
    tor = 0
    subs = models.Subscriber.mailing_list(topic).count()
    for year, week in yearweeks:
        orate = (
            models.Subscriber.mailing_list(topic)
            .filter(weeks_clicked__contains=[f"{year}{week}"])
            .count()
        )
        if subs > 0:
            tor += orate / subs * 100

    return round(tor / last_n, 2)


def topics_open_rate():
    choices = []
    for t, n in topics.topics_choices:
        if t == "laarc":
            continue
        choices.append((t, f"{n} ({open_rate(t)}%)"))
    return choices
