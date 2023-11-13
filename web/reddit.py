# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import io
import json
import logging
import os
import re
import shutil
import statistics
import time
from pathlib import Path

import cleanurl
import markdown
import praw
import praw.exceptions
import praw.models
import prawcore
import sentry_sdk
import zstandard
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django_redis import get_redis_connection

from discussions.settings import APP_CELERY_TASK_MAX_TIME

from . import celery_util, http, models, util, worker

logger = logging.getLogger(__name__)


# filled in apps.WebConfig.ready
subreddit_blacklist: set[str] = set()
subreddit_whitelist: set[str] = set()


def _url_blacklisted(url):
    if not url:
        return False

    if url.startswith(
        (
            "i.imgur.com",
            "imgur.com",
            "www.imgur.com",
            "gfycat.com",
            "www.gfycat.com",
            "i.redd.it",
            "reddit.com/live",
            "www.reddit.com/live",
            "reddit.com/gallery/",
            "www.reddit.com/gallery/",
            "preview.redd.it",
        ),
    ) or url in {
        "reddit.com",
        "reddit.com/",
        "www.reddit.com",
        "www.reddit.com/",
    }:
        return True

    return False


def __url_blacklisted_selftext(url):
    if not url:
        return False

    if (
        url
        in {
            "www.google.com",
            "google.com",
            "google.com/trends/explore",
            "www.privacytools.io/#photos",
            "example.com",
            "itch.io",
            "amazon.com",
            "github.com",
            "self.data",
            "self.name",
        }
        or url == "crates.io"
        or url == "crates.io/"
        or url == "inventwithpython.com/bigbookpython/"
        or url == "inventwithpython.com/bigbookpython"
        or url == "learnopengl.com"
        or url == "learnopengl.com/"
        or url.startswith(
            (
                "discord.gg/python",
                "reddit.com",
                "www.reddit.com",
                "old.reddit.com",
                "preview.redd.it",
            ),
        )
    ):
        return True

    return False


def _url_from_selftext(selftext, title=None):
    if not selftext:
        return None

    title = (title or "").strip().lower()
    if title.endswith("?"):
        return None

    if "help" in title:
        return None

    h = http.parse_html(markdown.markdown(selftext))
    if not h:
        return None

    links = []

    for a in h.select("a") or []:
        if a and a.get("href"):
            u = cleanurl.cleanurl(
                a["href"],
                generic=True,
                respect_semantics=True,
                host_remap=False,
            )
            if not u:
                continue
            if u.scheme not in {"http", "https", "ftp"}:
                continue
            if not u.parsed_url.netloc or not u.parsed_url.hostname:
                continue
            if _url_blacklisted(u.schemeless_url):
                continue
            if __url_blacklisted_selftext(u.schemeless_url):
                continue
            if u.schemeless_url.startswith(
                "reddit.com",
            ) or u.schemeless_url.startswith("www.reddit.com"):
                continue
            if re.match(r"^[0-9\.:]+$", u.parsed_url.netloc):
                continue
            if re.match(r"^\[[a-z0-9:]+\](:[0-9]+)?$", u.parsed_url.netloc):
                continue
            if u.parsed_url.hostname.lower() == "localhost":
                continue

            lower_netloc = u.parsed_url.netloc.lower()
            if (
                (lower_netloc.endswith((".py", ".rs", ".net", ".md")))
                and (not u.parsed_url.path or u.parsed_url.path == "/")
                and lower_netloc
                == util.strip_punctuation(
                    a.text.lower().replace(" ", ""),
                )
            ):
                continue

            links.append(a["href"])

    if len(links) == 1:
        return links[0]

    return None


def __process_archive_line(line):
    p = json.loads(line)
    if p.get("subreddit") not in subreddit_whitelist:
        return

    if p.get("over_18"):
        return
    if p.get("is_reddit_media_domain"):
        return
    if p.get("hidden"):
        return
    # if p.get("media"):
    if (p.get("score") or 0) < 1:
        return
    if (p.get("num_comments") or 0) <= 2:
        return

    platform_id = "r" + p.get("id")

    scheme, url, story_url = None, None, None
    if p.get("is_self"):
        url = _url_from_selftext(p.get("selftext"), p.get("title"))
    else:
        url = p.get("url")

    if url:
        u = cleanurl.cleanurl(
            url,
            generic=True,
            respect_semantics=True,
            host_remap=False,
        )
        scheme = u.scheme
        story_url = u.schemeless_url

    if _url_blacklisted(story_url):
        return

    created_at = None
    if p.get("created_utc"):
        created_at = datetime.datetime.fromtimestamp(
            int(p.get("created_utc")),
            tz=datetime.UTC,
        )

    subreddit = p.get("subreddit") or ""
    if not subreddit:
        logger.warning(f"Reddi archive: no subreddit {platform_id}")
        return

    _ = models.Discussion.objects.update_or_create(
        pk=platform_id,
        defaults={
            "comment_count": p.get("num_comments") or 0,
            "score": p.get("score") or 0,
            "created_at": created_at,
            "scheme_of_story_url": scheme,
            "schemeless_story_url": story_url,
            "title": p.get("title"),
            "tags": [subreddit.lower()],
        },
    )


def __get_reddit_archive_links(client, starting_from=None):
    url_prefix = "https://files.pushshift.io/reddit/submissions/"
    digests = client.get(url_prefix + "sha256sums.txt")
    available_files = []
    for line in digests.content.decode().split("\n"):
        fields = line.split()
        if len(fields) >= 2:
            available_files.append(fields[1])

    chosen_files = []

    for file in available_files:
        match = re.findall(r"RS.*(\d\d\d\d)-(\d\d)\.zst", file)[0]
        year_month = match[0] + "-" + match[1]

        if starting_from and year_month < starting_from:
            continue

        chosen_files.append(url_prefix + file)

    return chosen_files


@shared_task(bind=True, ignore_result=True)
def worker_fetch_reddit_archive(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    client = http.client(with_cache=False)
    cache_prefix = "fetch_reddit_archive"
    cache_timeout = 60 * 60 * 24 * 90

    for file in __get_reddit_archive_links(client):
        if cache.get(f"{cache_prefix}:processed:{file}"):
            continue

        if worker.graceful_exit(self):
            logger.info("reddit archive: graceful exit")
            break

        logger.info(f"reddit archive: processing {file}")

        file_name = "/tmp/discussions_reddit_archive_compressed"  # noqa: S108

        if not Path(file_name).is_file():
            _ = cache.delete(f"{cache_prefix}:downloaded:{file}")

        if not cache.get(f"{cache_prefix}:downloaded:{file}"):
            with client.get(file, stream=True) as res:
                logger.debug(f"reddit archive: start download {file}")
                with Path(file_name).open("wb") as f:
                    shutil.copyfileobj(res.raw, f)
                logger.debug(f"reddit archive: end download {file}")
                cache.set(
                    f"{cache_prefix}:downloaded:{file}",
                    1,
                    timeout=cache_timeout,
                )

        f = Path(file_name).open("rb")  # noqa: SIM115

        stream = zstandard.ZstdDecompressor(
            max_window_size=2**31,
        ).stream_reader(f, read_across_frames=True)

        text = io.TextIOWrapper(stream, encoding="utf-8")

        graceful_exit = False

        c = 0
        for line in text:
            if c % 1_000_000 == 0:
                logger.info(f"reddit archive: File {file}, line {c}")
                if worker.graceful_exit(self):
                    logger.info("reddit archive: graceful exit")
                    graceful_exit = True
                    break

            c += 1
            try:
                __process_archive_line(line)
            except Exception:  # noqa: BLE001
                logger.info(
                    "reddit archive: line failed: \n\n %s",
                    line,
                    exc_info=True,
                )

        stream.close()
        f.close()
        Path(file_name).unlink()

        if not graceful_exit:
            cache.set(
                f"{cache_prefix}:processed:{file}",
                1,
                timeout=cache_timeout,
            )

        time.sleep(5)


class EndOfSubreddits(Exception):  # noqa: N818
    pass


def client(username=None, password=None):
    return praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        user_agent=settings.USERAGENT,
        ratelimit_seconds=60 * 14,
        timeout=60,
        username=username,
        password=password,
    )


def client_username():
    return client(
        os.getenv("REDDIT_USERNAME"),
        os.getenv("REDDIT_PASSWORD"),
    )


def submit(subreddit, title, url=None, selftext=None, c=None):
    if not c:
        c = client_username()

    logger.debug(c.user.me())

    sub = c.subreddit(subreddit)

    story = None
    try:
        story = sub.submit(
            title=title,
            url=url,
            selftext=selftext,
            resubmit=False,
        )
    except praw.exceptions.PRAWException:
        logger.exception("Reddit submit")

    return story


def get_subreddit(
    subreddit,
    reddit_client,
    listing="new",
    listing_argument="",
    limit=100,
):
    subreddit = subreddit.lower()

    stories = set()
    story_list = []
    if listing == "new":
        story_list = reddit_client.subreddit(subreddit).new(limit=limit)
    if listing == "top":
        story_list = reddit_client.subreddit(subreddit).top(
            listing_argument,
            limit=limit,
        )

    for story in story_list:
        stories.add(story)

    return stories


def __process_post(p):
    platform_id = f"r{p.id}"

    if p.over_18:
        return

    if p.is_reddit_media_domain:
        return

    if p.hidden:
        return

    # if p.media:

    url = None
    if p.is_self:
        if not p.stickied:
            url = _url_from_selftext(p.selftext, p.title)
    else:
        url = p.url

    scheme, story_url = None, None
    if url:
        u = cleanurl.cleanurl(
            url,
            generic=True,
            respect_semantics=True,
            host_remap=False,
        )
        scheme = u.scheme
        story_url = u.schemeless_url

    if _url_blacklisted(story_url):
        return

    created_utc = p.created_utc
    if isinstance(created_utc, str):
        created_utc = int(created_utc)
    created_at = datetime.datetime.fromtimestamp(created_utc, tz=datetime.UTC)

    subreddit = p.subreddit.display_name.lower()

    try:
        discussion = models.Discussion.objects.get(pk=platform_id)
        discussion.comment_count = p.num_comments or 0
        discussion.score = p.score or 0
        discussion.created_at = created_at
        discussion.scheme_of_story_url = scheme
        discussion.schemeless_story_url = story_url
        discussion.title = p.title
        discussion.archived = p.archived
        discussion.tags = [subreddit]
        discussion.save()
    except models.Discussion.DoesNotExist:
        models.Discussion(
            platform_id=platform_id,
            comment_count=p.num_comments or 0,
            score=p.score or 0,
            created_at=created_at,
            scheme_of_story_url=scheme,
            schemeless_story_url=story_url,
            title=p.title,
            archived=p.archived,
            tags=[subreddit],
        ).save()


def search_url(
    url: str,
    c: praw.Reddit | None = None,
    sub: praw.models.Subreddit | None = None,
) -> None:
    if not url:
        return
    if not c:
        c = client()
    if not sub:
        sub = c.subreddit("all")

    submissions = sub.search(f'url:"{url}"')
    for s in submissions:
        __process_post(s)


def search_urls(url_pattern: str) -> None:
    reddit = client()
    subreddit_all = reddit.subreddit("all")
    urls = (
        models.Discussion.objects.filter(
            schemeless_story_url__icontains=url_pattern,
        )
        .values("schemeless_story_url")
        .distinct()
    )

    logger.debug(f"reddit search urls: count {urls.count()}")

    c = 0
    for url in urls:
        u = url.get("schemeless_story_url")
        if not u:
            continue
        search_url(u, reddit, subreddit_all)

    logger.debug(f"reddit search submissions: count {c}")


def fetch_discussions(index):
    reddit = client()
    skip_sub_key_prefix = "discussions:reddit:subreddit:skip:"

    start_time = time.monotonic()

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        if index >= len(subreddit_whitelist):
            raise EndOfSubreddits
        subreddit = sorted(subreddit_whitelist)[index]
        name = subreddit.lower()
        index += 1

        if cache.get(skip_sub_key_prefix + name):
            continue

        try:
            stories = get_subreddit(name, reddit)
        except (
            praw.exceptions.PRAWException,
            prawcore.exceptions.Forbidden,
            prawcore.exceptions.NotFound,
            prawcore.exceptions.PrawcoreException,
        ):
            logger.warning("reddit: subreddit %s", name, exc_info=True)
            cache.set(skip_sub_key_prefix + name, 1, timeout=60 * 60 * 8)
            continue

        created_at = []

        try:
            for p in stories:
                __process_post(p)
                if p.created_utc:
                    created_at.append(int(p.created_utc))
        except (
            prawcore.exceptions.Forbidden,
            prawcore.exceptions.NotFound,
            prawcore.exceptions.PrawcoreException,
        ) as e:
            logger.warning(f"reddit: subreddit {name}: {e}")
            cache.set(skip_sub_key_prefix + name, 1, timeout=60 * 60 * 8)
            continue

        created_at = sorted(created_at)
        created_at_diff = [
            created_at[i + 1] - created_at[i]
            for i in range(len(created_at) - 1)
        ]

        delay = statistics.median(created_at_diff) if created_at_diff else 0

        logger.debug(f"reddit update: {name}: median {delay}")

        delay = max(60 * 15, min(delay, 60 * 60 * 3))

        td = datetime.timedelta(seconds=delay)
        logger.debug(f"reddit update: {name}: delay {td}")

        cache.set(skip_sub_key_prefix + name, 1, timeout=delay)

    return index


@shared_task(bind=True, ignore_result=True)
def fetch_recent_discussions(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    r = get_redis_connection("default")
    redis_prefix = "discussions:fetch_recent_reddit_discussions:"
    current_index = int(r.get(redis_prefix + "current_index") or 0)
    max_index = int(r.get(redis_prefix + "max_index") or 0)
    if not max_index or (current_index > max_index):
        max_index = len(subreddit_whitelist)
        r.set(redis_prefix + "max_index", max_index)
        current_index = 0

    try:
        current_index = fetch_discussions(current_index)
    except EndOfSubreddits:
        current_index = max_index + 1

    r.set(redis_prefix + "current_index", current_index)


@shared_task(bind=True, ignore_result=True)
def worker_update_all_discussions(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    reddit = client()
    cache_current_index_key = "discussions:reddit_update:current_index"
    current_index = cache.get(cache_current_index_key) or 0

    logger.debug(f"reddit update all: current index: {current_index}")

    q = (
        models.Discussion.objects.filter(_platform="r")
        .filter(archived=False)
        .order_by("pk")
    )

    logger.debug(f"reddit update all: count {q.count()}")

    while True:
        if worker.graceful_exit(self):
            logger.info("reddit update all: graceful exit")
            break

        ps = []
        ds = []
        query_has_results = False

        step = 100

        logger.debug(f"reddit update all: current index {current_index}")

        for d in q[current_index : current_index + step]:
            if d.subreddit.lower() in subreddit_blacklist:
                _ = d.delete()
                continue
            if _url_blacklisted(
                d.canonical_story_url or d.schemeless_story_url,
            ):
                _ = d.delete()
                continue

            query_has_results = True
            ps.append(f"t3_{d.id}")
            ds.append(d)

        if not query_has_results:
            logger.debug(
                f"reddit update all: query with no results: {current_index}",
            )
            current_index = 0
            cache.set(cache_current_index_key, current_index, timeout=None)
            continue

        try:
            submissions = reddit.info(ps)
            for s in submissions:
                _ = s.title  # preload
        except (
            praw.exceptions.PRAWException,
            prawcore.exceptions.PrawcoreException,
        ) as e:
            logger.exception("reddit update all: reddit.info")
            _ = sentry_sdk.capture_exception(e)
            submissions = []
            time.sleep(60)

        for i, p in enumerate(submissions):
            d = ds[i]

            if p.over_18:
                d.delete()
                continue

            url = None

            if p.is_self:
                if not p.stickied:
                    url = _url_from_selftext(p.selftext, p.title)
            else:
                url = p.url

            scheme, story_url = None, None
            if url:
                u = cleanurl.cleanurl(
                    url,
                    generic=True,
                    respect_semantics=True,
                    host_remap=False,
                )
                scheme = u.scheme
                story_url = u.schemeless_url

            if _url_blacklisted(story_url):
                d.delete()
                continue

            d.comment_count = p.num_comments or 0
            d.score = p.score or 0
            d.title = p.title
            d.archived = p.archived
            d.scheme_of_story_url = scheme
            d.schemeless_story_url = story_url

            d.save()

        current_index += step

        cache.set(cache_current_index_key, current_index, timeout=None)

        time.sleep(5)


@shared_task(bind=True, ignore_result=True)
def worker_stream(self):
    if celery_util.task_is_running(self.request.task, [self.request.id]):
        return
    reddit = client()

    subs = "+".join(subreddit_whitelist)

    for p in reddit.subreddit(subs).stream.submissions(pause_after=0):
        if p:
            __process_post(p)
        if worker.graceful_exit(self):
            logger.info("reddit stream: graceful exit")
            break
