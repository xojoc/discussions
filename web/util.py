# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import os
import unicodedata
from collections.abc import Callable
from difflib import SequenceMatcher
from urllib.parse import quote, quote_plus

import cleanurl
from django.urls import reverse
from django.utils import timezone

from discussions import settings


def path_with_domain(path):
    return f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}{path}"


def discussions_url(q, *, with_domain=True):
    if not q:
        q = ""
    path = "/q/" + quote(q, safe="/:?&=")
    if with_domain:
        return f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}{path}"
    return path


def discussions_canonical_url(q, *, with_domain=True):
    if not q:
        q = ""
    q = q.lower()

    cu = cleanurl.cleanurl(q)

    if cu and cu.scheme in {"http", "https"}:
        q = cu.url or ""
        q = q.replace("http://", "https://")

    return discussions_url(q, with_domain=with_domain)


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def __noop(a):
    return a


def most_similar(
    bs: list[str],
    a: str,
    key: Callable[[str], str] = __noop,
) -> str | None:
    if not bs:
        return None
    return max({(similarity(a, key(b)), b) for b in bs}, key=lambda x: x[0])[1]


def is_dev():
    return os.getenv("DJANGO_DEVELOPMENT", "").lower() == "true"


def strip_punctuation(w):
    while len(w) > 0:
        cat = unicodedata.category(w[0])
        if cat.startswith("P"):
            w = w[1:]
        else:
            break

    while len(w) > 0:
        cat = unicodedata.category(w[-1])
        if cat.startswith("P"):
            w = w[:-1]
        else:
            break

    return w


def url_root(url: str | cleanurl.Result | None) -> str | None:
    """Return the *root* of the page."""
    if isinstance(url, str):
        url = cleanurl.cleanurl(
            url,
            generic=True,
            respect_semantics=True,
            host_remap=False,
        )

    if not url:
        return None

    atleast_for_project = 2
    if url.hostname in {
        "www.github.com",
        "github.com",
        "gitlab.com",
        "www.gitlab.com",
    }:
        parts = (url.path or "").split("/")
        parts = [p for p in parts if p]
        if len(parts) >= atleast_for_project:
            return url.hostname + "/" + parts[0]

    atleast_for_post = 3
    if url.hostname in {
        "www.twitter.com",
        "twitter.com",
        "mobile.twitter.com",
    }:
        parts = (url.path or "").split("/")
        parts = [p for p in parts if p]
        if len(parts) >= atleast_for_post and parts[1] == "status":
            return url.hostname + "/" + parts[0]

    if url.hostname in {
        "mastodon.social",
        "mastodon.technology",
    }:
        parts = (url.path or "").split("/")
        parts = [p for p in parts if p]
        if (
            len(parts) >= atleast_for_post
            and parts[0] == "web"
            and parts[1][0] == "@"
        ):
            return url.hostname + "/web/" + parts[1]

    return url.hostname


def is_sublist(lst, sublist):
    for i in range(len(lst) - len(sublist) + 1):
        for j in range(len(sublist)):
            if lst[i + j] != sublist[j]:
                break
        else:
            return True
    return False


def days_ago(days):
    return timezone.now() - datetime.timedelta(days=days)


def click_url(url, subscriber=None, topic=None, year=None, week=None):
    path = reverse("web:click")
    path += f"?url={quote_plus(url)}"
    if subscriber:
        path += f"&subscriber={subscriber.pk}"
    if topic:
        path += f"&topic={topic}"
    if year:
        path += f"&year={year}"
    if week:
        path += f"&week={week}"

    return path_with_domain(path)
