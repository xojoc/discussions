from web import models
import datetime
from django.utils.timezone import make_aware
from django.db.models.functions import TruncDay
import logging
import urllib3

logger = logging.getLogger(__name__)

topics = {
    "rust": {
        "name": "Rust language",
        "short_description": "Rust programming language",
        "tags": ["rustlang"],
    },
    "compsci": {
        "name": "Computer science",
        "short_description": "Computer science",
        "tags": ["compsci"],
    },
    "devops": {
        "name": "DevOps",
        "short_description": "DevOps",
        "tags": {"devops", "docker", "kubernets"},
    },
}

for topic_key, topic in topics.items():
    topic["email"] = f"weekly_{topic_key}@discu.eu"

topics_choices = sorted([(key, item["name"]) for key, item in topics.items()])


def __category(story):
    u = urllib3.util.parse_url(story.canonical_story_url)
    path = u.path or ""
    title_tokens = story.normalized_title.split()

    if "programming" in story.normalized_tags:
        if "release" in title_tokens or "released" in title_tokens:
            return "release"

    if u.host in ("github.com", "gitlab.com", "bitbucket.org", "gitea.com"):
        parts = [p for p in path.split("/") if p]
        if len(parts) == 2:
            return "project"

    if u.host in ("savannah.gnu.org", "savannah.nongnu.org"):
        if path.startswith("/projects/"):
            return "project"

    if u.host in ("crates.io"):
        if path.startswith("/crates/"):
            return "project"

    return "generic"


def __base_query(topic):
    tags = topics[topic]["tags"]
    return (
        models.Discussion.objects.filter(normalized_tags__overlap=tags)
        .exclude(schemeless_story_url__isnull=True)
        .exclude(schemeless_story_url="")
        .exclude(scheme_of_story_url__isnull=True)
        .exclude(created_at__isnull=True)
    )


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
        .order_by("created_at")
    )

    logger.debug(f"weekly: stories count {stories.count()}")

    for story in stories:
        category = __category(story)
        story.__dict__["category"] = category
        r = models.Resource.by_url(story.schemeless_story_url)
        if r:
            irs = r.inbound_resources()
            story.__dict__["related_articles"] = irs.values()

    return stories


def index_context():
    ctx = {}
    ctx["topics"] = topics
    return ctx


def topic_context(topic):
    ctx = {}
    ctx["topic_key"] = topic
    ctx["topic"] = topics[topic]
    ctx["yearweeks"] = []
    yearweeks = all_yearweeks(topic)
    for yearweek in yearweeks:
        ctx["yearweeks"].append(
            {
                "year": yearweek[0],
                "week": yearweek[1],
                "week_start": week_start(yearweek),
                "week_end": week_end(yearweek),
            }
        )
    return ctx


def topic_week_context(topic, year, week):
    ctx = {}
    ctx["topic_key"] = topic
    ctx["topic"] = topics[topic]
    ctx["year"] = year
    ctx["week"] = week
    ctx["week_start"] = week_start(year, week)
    ctx["week_end"] = week_end(year, week)
    ctx["stories"] = __get_stories(topic, year, week)
    return ctx


# Weekly digests

# [email] Get future digests straight to your inbox


# This week's digest


# 01 2019
# 02 2019
# 03 2019
# ...


# 01 2018
