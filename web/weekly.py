from web import models
import datetime
from django.utils.timezone import make_aware
import logging
import urllib3

logger = logging.getLogger(__name__)

topics = {
    "rust": {
        "tags": ["rustlang"],
    }
}


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


def __get(topic, week, year):
    import django

    django.db.connections.close_all()

    week_start = datetime.date.fromisocalendar(year, week, 1)
    week_start = datetime.datetime.combine(week_start, datetime.time(0, 0))
    week_start = make_aware(week_start)
    week_end = week_start + datetime.timedelta(days=7)
    week_end = datetime.datetime.combine(week_end, datetime.time(0, 0))
    week_end = make_aware(week_end)

    logger.debug(f"weekly: date range {topic} {week_start} {week_end}")

    tags = topics[topic]["tags"]

    stories = (
        models.Discussion.objects.filter(created_at__gte=week_start)
        .filter(created_at__lt=week_end)
        .filter(normalized_tags__overlap=tags)
        .exclude(schemeless_story_url__isnull=True)
        .exclude(schemeless_story_url="")
        .exclude(scheme_of_story_url__isnull=True)
        .order_by("created_at")
    )

    logger.debug(f"weekly: stories count {stories.count()}")

    for story in stories:
        print(story.created_at)
        print(story.title)
        print(story.story_url)
        category = __category(story)
        print(category)
        r = models.Resource.by_url(story.schemeless_story_url)
        if r:
            irs = r.inbound_resources()
            for ir in irs:
                print(f" -> ir: {ir.title}")
                print(f" -> ir: {ir.complete_url}")


# Weekly digests

# [email] Get future digests straight to your inbox


# This week's digest


# 01 2019
# 02 2019
# 03 2019
# ...


# 01 2018
