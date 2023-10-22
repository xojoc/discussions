# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import logging
import re
import time

import bs4
import cleanurl
from celery import shared_task
from django.utils.timezone import make_aware
from django_redis import get_redis_connection

from discussions.settings import APP_CELERY_TASK_MAX_TIME
from web import celery_util, http, models, util

logger = logging.getLogger(__name__)

# http://lambda-the-ultimate.org/node?from=0


class EndOfPagesError(Exception):
    pass


def __filter_story_url(a):
    if not a:
        return False
    href = a.get("href")
    if not href:
        return False

    href = href.removeprefix("https://")
    href = href.removeprefix("http://")

    if not href:
        return False

    return not (
        href.startswith(("duckduckgo.", "google.", "lambda-the-ultimate."))
    )


def process_item(item: bs4.BeautifulSoup, platform_prefix: str) -> None:
    try:
        slug = item.select_one(".title a").get("href").strip()
    except AttributeError:
        slug = None

    platform_id = f"{platform_prefix}{slug}"

    try:
        title = item.select_one(".title").get_text().strip()
    except AttributeError:
        return

    comment_count = 0
    score = 0

    for link in item.select(".links a"):
        if not comment_count:
            try:
                comment_count = re.match(
                    r"(\d+) comment",
                    link.get_text().strip().lower(),
                ).group(1)
                comment_count = int(comment_count)
            except (AttributeError, IndexError):
                comment_count = 0

    try:
        score = re.match(
            r".* (\d+) reads",
            item.select_one(".links").get_text().strip().lower(),
        ).group(1)
        score = int(score)
    except (AttributeError, IndexError):
        score = 0

    tags = [
        x.get_text().strip()
        for x in item.select('.links a[href^="taxonomy/"]')
    ]

    body_links = item.select(".content a")

    if not body_links or len(body_links) == 0:
        return

    body_links = list(filter(__filter_story_url, body_links))

    if not body_links or len(body_links) == 0:
        if not any(t.lower() == "admin" for t in tags):
            logger.warning(f"LTU: no links after filter {platform_id}")
        return

    story_url = None

    if len(body_links) == 1:
        story_url = body_links[0].get("href")

    if len(body_links) > 1:
        story_url = util.most_similar(
            body_links,
            title,
            key=lambda x: x.get_text(),
        )
        story_url = story_url.get("href")

    if not story_url:
        return

    try:
        created_at = re.match(
            r".* at (\d\d\d\d-\d\d-\d\d \d\d:\d\d)",
            item.select_one(".links").get_text(),
        ).group(1)

        created_at = datetime.datetime.fromisoformat(created_at)
        created_at = make_aware(created_at)
    except (AttributeError, IndexError):
        created_at = None

    scheme, url = None, None
    u = cleanurl.cleanurl(
        story_url,
        generic=True,
        respect_semantics=True,
        host_remap=False,
    )
    if u:
        scheme = u.scheme
        url = u.schemeless_url

    try:
        discussion = models.Discussion.objects.get(pk=platform_id)

        discussion.comment_count = comment_count
        discussion.score = score
        discussion.created_at = created_at
        discussion.scheme_of_story_url = scheme
        discussion.schemeless_story_url = url
        discussion.title = title
        discussion.tags = tags
        discussion.save()
    except models.Discussion.DoesNotExist:
        models.Discussion(
            platform_id=platform_id,
            comment_count=comment_count,
            score=score,
            created_at=created_at,
            scheme_of_story_url=scheme,
            schemeless_story_url=url,
            title=title,
            tags=tags,
        ).save()


def fetch_discussions(current_page, platform_prefix, base_url):
    c = http.client(with_cache=False)

    start_time = time.monotonic()

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        page_url = f"{base_url}/node?from={current_page * 10}"

        r = c.get(page_url, timeout=11.05)

        h = http.parse_html(r)

        body = h.get_text().lower().strip()
        body = " ".join(body.split())

        if (
            r.status_code == 404
            or body.find("welcome to your new drupal-powered") >= 0
        ):
            raise EndOfPagesError

        for item in h.find_all("div", "node"):
            process_item(item, platform_prefix)

        current_page += 1

        time.sleep(2.1)

    return current_page


@shared_task(bind=True, ignore_result=True)
def fetch_all_ltu_discussions(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    r = get_redis_connection("default")
    redis_prefix = "discussions:ltu:fetch_all_discussions:"
    current_index = r.get(redis_prefix + "current_index")
    max_index = int(r.get(redis_prefix + "max_index") or 0)
    if (
        current_index is None
        or not max_index
        or (int(current_index) > max_index)
    ):
        max_index = 1_000_000_000
        r.set(redis_prefix + "max_index", max_index)
        current_index = 0

    current_index = int(current_index)

    try:
        current_index = fetch_discussions(
            current_index,
            "u",
            "http://lambda-the-ultimate.org",
        )
    except EndOfPagesError:
        current_index = max_index + 1

    r.set(redis_prefix + "current_index", current_index)


@shared_task(ignore_result=True)
def process_ltu_archived_item(item_href, base_url, platform_prefix, c):
    item = http.parse_html(c.get(f"{base_url}/{item_href}"))

    try:
        story = item.select_one("td[bgcolor] b a[href]")
    except AttributeError:
        return

    if not story:
        return

    platform_id = f"{platform_prefix}classic/{item_href}"

    title = story.get_text().strip()

    comment_count = 0
    score = 0
    created_at = None

    for td in item.select("tr[bgcolor] td"):
        txt = td.get_text().strip().lower()
        if not comment_count:
            try:
                comment_count = re.match(
                    r".*responses: (\d+).*",
                    txt,
                    re.DOTALL,
                ).group(1)
                comment_count = int(comment_count)
            except (AttributeError, IndexError):
                comment_count = 0

        if not score:
            try:
                score = re.match(r".*reads: (\d+).*", txt, re.DOTALL).group(1)
                score = int(score)
            except (AttributeError, IndexError):
                score = 0

        if not created_at:
            try:
                tst_match = re.search(
                    r"(\d+/\d+/\d\d\d\d); (\d+:\d+:\d+ ..)",
                    txt,
                    re.DOTALL,
                )

                date_match = tst_match.group(1)
                time_match = tst_match.group(2).upper()
                created_at = datetime.datetime.strptime(
                    f"{date_match} {time_match}",
                    "%m/%d/%Y %I:%M:%S %p",
                ).replace(tzinfo=datetime.UTC)
            except (ValueError, AttributeError, IndexError):
                created_at = None

    if comment_count:
        comment_count += 1

    story_url = story.get("href")
    if not story_url:
        return

    tags = (
        [
            x.get_text().strip()
            for x in item.select('b a:not([href*="/"])[href$=".html"]')
        ]
        if item
        else []
    )

    scheme, url = None, None
    u = cleanurl.cleanurl(
        story_url,
        generic=True,
        respect_semantics=True,
        host_remap=False,
    )
    if u:
        scheme = u.scheme
        url = u.schemeless_url

    try:
        discussion = models.Discussion.objects.get(pk=platform_id)

        discussion.comment_count = comment_count
        discussion.score = score
        discussion.created_at = created_at
        discussion.scheme_of_story_url = scheme
        discussion.schemeless_story_url = url
        discussion.title = title
        discussion.tags = tags
        discussion.save()
    except models.Discussion.DoesNotExist:
        models.Discussion(
            platform_id=platform_id,
            comment_count=comment_count,
            score=score,
            created_at=created_at,
            scheme_of_story_url=scheme,
            schemeless_story_url=url,
            title=title,
            tags=tags,
        ).save()


def fetch_ltu_archived_discussions(current_page, platform_prefix, base_url):
    c = http.client(with_cache=False)

    start_time = time.monotonic()

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        page_url = f"{base_url}/lambda-archive{current_page}.html"

        r = c.get(page_url, timeout=11.05)

        if r.status_code == 404:
            raise EndOfPagesError

        h = http.parse_html(r)

        for item in h.select("table tr td a"):
            process_ltu_archived_item(
                item.get("href"),
                base_url,
                platform_prefix,
                c,
            )

        current_page += 1

        time.sleep(2.1)

    return current_page


@shared_task(bind=True, ignore_result=True)
def fetch_all_ltu_archived_discussions(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    r = get_redis_connection("default")
    redis_prefix = "discussions:ltu:archived:fetch_all_discussions:"
    current_index = r.get(redis_prefix + "current_index")
    max_index = int(r.get(redis_prefix + "max_index") or 0)
    if (
        current_index is None
        or not max_index
        or (int(current_index) > max_index)
    ):
        max_index = 1_000_000_000
        r.set(redis_prefix + "max_index", max_index)
        current_index = 1

    current_index = int(current_index)

    try:
        current_index = fetch_ltu_archived_discussions(
            current_index,
            "u",
            "http://lambda-the-ultimate.org/classic",
        )
    except EndOfPagesError:
        current_index = max_index + 1

    r.set(redis_prefix + "current_index", current_index)
