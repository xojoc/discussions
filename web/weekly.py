import datetime
import itertools
import logging
import random
import re

import django.template.loader as template_loader
import urllib3
from celery import shared_task
from django.db.models import Count, Sum
from django.db.models.functions import TruncDay, Coalesce
from django.urls import reverse
from django.utils.timezone import make_aware

from discussions import settings

from . import celery_util, email_util, mastodon, models, topics

logger = logging.getLogger(__name__)

categories = {
    "article": {
        "name": "Articles",
        "sort": 10,
    },
    "release": {
        "name": "Releases",
        "sort": 20,
    },
    "project": {
        "name": "Projects",
        "sort": 30,
    },
    "video": {
        "name": "Videos",
        "sort": 40,
    },
}


def __category(story):
    u = urllib3.util.parse_url(story.canonical_story_url)
    path, host = "", ""
    if u:
        path = u.path or ""
        host = u.host or ""
    title_tokens = story.normalized_title.split()

    if "programming" in story.normalized_tags:
        if "release" in title_tokens or "released" in title_tokens:
            return "release"
    if "release" in story.normalized_tags:
        return "release"

    if host in ("github.com", "gitlab.com", "bitbucket.org", "gitea.com"):
        parts = [p for p in path.split("/") if p]
        if len(parts) == 2:
            return "project"

    if host in ("savannah.gnu.org", "savannah.nongnu.org"):
        if path.startswith("/projects/"):
            return "project"

    if host in ("crates.io"):
        if path.startswith("/crates/"):
            return "project"

    # fixme: look for parameters too
    if host in ("youtu.be", "youtube.com", "vimeo.com"):
        return "video"

    return "article"


def __base_query(topic):
    qs = (
        models.Discussion.objects.exclude(schemeless_story_url__isnull=True)
        .exclude(schemeless_story_url="")
        .exclude(scheme_of_story_url__isnull=True)
        .exclude(scheme_of_story_url="")
        .exclude(created_at__isnull=True)
    )
    tags = topics.topics[topic].get("tags")
    if tags:
        qs = qs.filter(normalized_tags__overlap=list(tags))
    if topics.topics[topic].get("platform"):
        qs = qs.filter(platform=topics.topics[topic].get("platform"))

    return qs


def week_start(year, week=None):
    if not week:
        year, week = year

    d = datetime.date.fromisocalendar(year, week, 1)
    d = datetime.datetime.combine(d, datetime.time(0, 0))
    d = make_aware(d)
    return d


def week_end(year, week=None):
    if not week:
        year, week = year

    d = week_start(year, week) + datetime.timedelta(days=7)
    d = datetime.datetime.combine(d, datetime.time(0, 0))
    d = make_aware(d)
    return d


def all_yearweeks(topic):
    yearweeks = set()
    stories = (
        __base_query(topic)
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
    days_ago = datetime.datetime.now() - datetime.timedelta(days=(n * 1.3) * 7)
    yearweeks = set()
    stories = (
        __base_query(topic)
        .filter(created_at__gte=days_ago)
        .annotate(created_at_date=TruncDay("created_at"))
        .values("created_at_date")
        .distinct()
        .order_by()
    )
    for s in stories.iterator():
        ic = s["created_at_date"].isocalendar()
        yearweeks.add((ic.year, ic.week))

    return sorted(yearweeks, reverse=True)[:n]


def __get_stories(topic, year, week):
    # import django

    # django.db.connections.close_all()

    ws = week_start(year, week)
    we = week_end(year, week)

    logger.debug(f"weekly: date range {topic} {ws} {we}")

    stories = (
        __base_query(topic)
        .filter(created_at__gte=ws)
        .filter(created_at__lt=we)
        .distinct("canonical_story_url")
        # .order_by("comment_count")
        # .order_by("created_at")
    )

    logger.debug(f"weekly: stories count {stories.count()}")

    for story in stories:
        category = __category(story)
        story.__dict__["category"] = category

        discussions, _, _ = models.Discussion.of_url(
            story.story_url, only_relevant_stories=True
        )
        discussion_counts = (
            discussions.aggregate(
                total_comments=Coalesce(Sum("comment_count"), 0),
                total_discussions=Coalesce(Count("platform_id"), 0),
            )
            or {}
        )
        story.__dict__["total_comments"] = discussion_counts.get(
            "total_comments"
        )
        story.__dict__["total_discussions"] = discussion_counts.get(
            "total_discussions"
        )

        # story.__dict__["discussions"], _, _ = models.Discussion.of_url(
        #     story.story_url, only_relevant_stories=True
        # )
        # r = models.Resource.by_url(story.schemeless_story_url)
        # if r:
        #     irs = r.inbound_resources()
        #     story.__dict__["related_articles"] = irs.values()

    return stories


def _get_digest(topic, year, week):
    stories = __get_stories(topic, year, week)
    stories = sorted(stories, key=lambda x: x.category)
    digest = [
        (category, categories[category]["name"], list(stories))
        for category, stories in itertools.groupby(
            stories, lambda x: x.category
        )
    ]

    digest = sorted(digest, key=lambda x: categories[x[0]]["sort"])

    for category, category_name, stories in digest:
        stories.sort(key=lambda x: x.total_comments, reverse=True)

        if category == "article":
            stories[:] = stories[:15]
        elif category == "project":
            stories[:] = stories[:10]
        elif category == "release":
            stories[:] = stories[:10]
        elif category == "video":
            stories[:] = stories[:7]
    return digest


def __generate_breadcrumbs(topic=None, year=None, week=None):
    breadcrumbs = []
    breadcrumbs.append({"name": "Home", "url": "/"})
    breadcrumbs.append(
        {
            "name": "Weekly newsletter",
            "url": reverse("web:weekly_index"),
            # "classes": "bold",
        }
    )
    if topic:
        breadcrumbs.append(
            {
                "name": topics.topics[topic]["name"],
                "url": reverse("web:weekly_topic", args=[topic]),
            }
        )
    if topic and year and week:
        breadcrumbs.append(
            {
                "name": f"Week {week}/{year}",
                "url": reverse(
                    "web:weekly_topic_week", args=[topic, year, week]
                ),
            }
        )

    # breadcrumbs[-1]["url"] = None

    for breadcrumb in breadcrumbs:
        if breadcrumb.get("url"):
            breadcrumb[
                "url"
            ] = f'{settings.APP_SCHEME}://{settings.APP_DOMAIN}{breadcrumb["url"]}'

    return breadcrumbs


def index_context():
    ctx = {}
    ctx["topics"] = topics.topics
    ctx["breadcrumbs"] = __generate_breadcrumbs()
    return ctx


def topic_context(topic):
    ctx = {}
    ctx["topic_key"] = topic
    ctx["topic"] = topics.topics[topic]
    ctx["yearweeks"] = []
    # yearweeks = all_yearweeks(topic)
    yearweeks = last_nth_yearweeks(topic, 10)
    for yearweek in yearweeks:
        ctx["yearweeks"].append(
            {
                "year": yearweek[0],
                "week": yearweek[1],
                "week_start": week_start(yearweek),
                "week_end": week_end(yearweek),
            }
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
            mastodon_cfg.get("account")
        )

    return ctx


def topic_week_context(topic, year, week):
    ctx = {}
    ctx["topic_key"] = topic
    ctx["topic"] = topics.topics[topic]
    ctx["year"] = year
    ctx["week"] = week
    ctx["week_start"] = week_start(year, week)
    ctx["week_end"] = week_end(year, week)
    # ctx["stories"] = __get_stories(topic, year, week)
    ctx["digest"] = _get_digest(topic, year, week)
    ctx["breadcrumbs"] = __generate_breadcrumbs(topic, year, week)
    ctx[
        "web_link"
    ] = f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}" + reverse(
        "web:weekly_topic_week", args=[topic, year, week]
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
            mastodon_cfg.get("account")
        )
    return ctx


def imap_handler(message, message_id, from_email, to_email, subject, body):
    logger.debug(
        f"""
    Message_id: {message_id}
    From: {from_email}
    To: {to_email}
    Subject: {subject}
    ---
    {body}
    """
    )

    try:
        topic_key = re.search(r"weekly_([a-z0-9]+)@discu\.eu", to_email)[1]
    except Exception:
        return False

    topic = topics.topics.get(topic_key)
    if not topic:
        return False

    if settings.EMAIL_TO_PREFIX and not to_email.startswith(
        settings.EMAIL_TO_PREFIX
    ):
        logger.debug(f"Weekly email NOT dev: '{topic_key}' '{from_email}'")
        return False

    tokens = body.lower().strip().split()
    if len(tokens) > 0 and tokens[0] == "subscribe":
        try:
            subscriber = models.Subscriber.objects.get(
                topic=topic_key, email=from_email
            )
            if subscriber.confirmed and not subscriber.unsubscribed:
                subscriber = None
                logger.info(
                    f"Subsription exists for {from_email} topic {topic_key}"
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
                f"Confirmation email sent to {from_email} topic {topic_key}"
            )
            return True

    if len(tokens) > 0 and tokens[0] == "unsubscribe":
        try:
            subscriber = models.Subscriber.objects.get(
                topic=topic_key, email=from_email
            )
        except models.Subscriber.DoesNotExist:
            logger.info(
                f"No subscription found for '{topic_key}' '{from_email}'"
            )
            subscriber = None

        if subscriber:
            subscriber.unsubscribe()
            subscriber.save()
            subscriber.send_unsubscribe_confirmation_email()
            logger.info(
                f"Unsubscribtion email sent to {from_email} topic {topic_key}"
            )
            return True

    return False


@shared_task(ignore_result=True)
def send_mass_email(topic, year, week, testing=True):
    subscribers = list(models.Subscriber.mailing_list(topic))
    random.shuffle(subscribers)

    logger.info(
        f"weekly: sending mail to {len(subscribers)} subscribers for {topic} {week}/{year}"
    )
    ctx = topic_week_context(topic, year, week)

    if not ctx.get("digest"):
        logger.warning(f"weekly: no articles {topic} {week}/{year}")
        return

    for subscriber in subscribers:
        ctx["subscriber"] = subscriber
        body = template_loader.render_to_string(
            "web/weekly_topic_digest.txt",
            {"ctx": ctx},
        )

        if testing:
            print(body)
        else:
            email_util.send(
                f"Weekly {topics.topics[topic]['name']} digest for week {week}/{year}",
                body,
                topics.topics[topic]["email"],
                subscriber.email,
            )


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_send_weekly_email(self):
    six_days_ago = datetime.datetime.now() - datetime.timedelta(days=6)
    year = six_days_ago.isocalendar().year
    week = six_days_ago.isocalendar().week

    for topic in topics.topics:
        send_mass_email.delay(topic, year, week, testing=False)
