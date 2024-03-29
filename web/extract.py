# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import contextlib
import logging
import urllib
import urllib.parse

import cleanurl
from bs4 import BeautifulSoup, Tag

from . import http

logger = logging.getLogger(__name__)


class Author:
    name = None
    twitter_account = None
    twitter_site = None
    mastodon_account = None
    mastodon_site = None
    homepage = None


# Page type:
#   Article
#   ArticleIndex
#   wikipedia
#   Github
#   Video (Viemo, youtube, streamja, etc.)


# TODO: use dataclass
class Structure:
    page_type = None
    title = None
    article: Tag | None = None
    tags = None
    number_of_comments = None
    commnets_seciton = None
    permanent_url = None
    publication_date = None
    edit_date = None
    author: Author | None = None
    outbound_links = []  # noqa: RUF012


def __extract_author(h):
    author = Author()

    if h:
        author.twitter_account = (
            h.select_one(
                'meta[name="twitter:creator"], meta[property="twitter:creator"]',
            )
            or {}
        ).get("content", "").removeprefix("@") or None

        author.twitter_site = (
            h.select_one(
                'meta[name="twitter:site"], meta[property="twitter:site"]',
            )
            or {}
        ).get("content", "").removeprefix("@") or None

    if author.twitter_account:
        parts = author.twitter_account.split("/")
        parts = [p for p in parts if p]
        author.twitter_account = parts[-1]
        author.twitter_account = author.twitter_account.strip()

        author.twitter_account = author.twitter_account.removeprefix("@")

        if " " in author.twitter_account:
            author.twitter_account = None

    if author.twitter_site:
        parts = author.twitter_site.split("/")
        parts = [p for p in parts if p]
        author.twitter_site = parts[-1] if parts else ""
        author.twitter_site = author.twitter_site.strip()

        author.twitter_site = author.twitter_site.removeprefix("@")

        if " " in author.twitter_site:
            author.twitter_site = None

    # if not author.twitter_account:
    #     if article:
    #     if h:

    #     for t in twitter_links:
    #         if len(parts) == 2:
    #             if parts[0] not in ('twitter.com', 'm.twitter.com', 'mobile.twitter.com', 'www.twitter.com'):
    #             if '?' in parts[1] or '&' in parts[1]:
    #             if parts[1] in ('signup', 'login', 'signin', 'about', 'share'):

    #     if len(possible_accounts) == 1:
    #         if author.twitter_account.lower() == (author.twitter_site or '').lower():

    return author


def __extract_title(h, s, url):
    if not s.title:
        with contextlib.suppress(Exception):
            s.title = h.select_one("title").get_text().strip()

    nt = (s.title or "").strip(" -:~").lower()

    u = cleanurl.cleanurl(url)

    if u:
        if u.hostname == "youtu.be" and nt == "youtube":
            s.title = None

        if u.hostname == "godbolt.org":
            s.title = None

        if u.hostname == "v.fodder.gg":
            s.title = None

        if u.hostname == "streamff.com":
            s.title = None

        if u.hostname == "streamgg.com":
            s.title = None

        if u.hostname in {"clips.twitch.tv", "twitch.tv"}:
            s.title = None

        # TODO: blocked in EU. Skip for now
        if u.hostname == "nydailynews.com":
            s.title = None

        # TODO: requires login
        if u.hostname == "instagram.com":
            s.title = None

        if u.hostname == "reddit-stream.com":
            s.title = None


def structure(
    h: str | BeautifulSoup | None,
    url: str | None = None,
) -> Structure:
    if isinstance(h, str):
        h = http.parse_html(h, safe_html=True)

    s = Structure()

    if not h:
        return s

    articles = h.select("article")
    if len(articles) == 1:
        s.article = articles[0]

    if s.article:
        s.outbound_links = s.article.select("a") or []

    s.author = __extract_author(h)

    __extract_title(h, s, url)

    return s


def fetch_parse_extract(u: str) -> Structure | None:
    r = http.fetch(u)
    if not r:
        return None
    h = http.parse_html(r.content)
    return structure(h, u)


def get_github_user_twitter(url):
    if not url:
        return None

    u = None
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return None

    if not u:
        return None

    if u.netloc not in {"github.com", "www.github.com"}:
        return None

    if not u.path:
        return None

    parts = u.path.split("/")

    if len(parts) < 3:
        return None

    api_url = f"https://api.github.com/repos/{parts[1]}/{parts[2]}"

    response = http.fetch(
        api_url,
        timeout=30,
        with_retries=False,
        with_cache=True,
    )

    if not response or not response.ok:
        return None

    js = response.json()
    if not js.get("owner"):
        return None

    if not js.get("owner").get("url"):
        return None

    response = http.fetch(
        js.get("owner").get("url"),
        timeout=30,
        with_retries=False,
        with_cache=True,
    )
    if not response or not response.ok:
        return None

    return response.json().get("twitter_username")
