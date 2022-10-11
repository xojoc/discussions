import os
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import quote

import cleanurl

from discussions import settings


def path_with_domain(path):
    return f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}{path}"


def discussions_url(q, with_domain=True):
    if not q:
        q = ""
    path = "/q/" + quote(q, safe="/:?&=")
    if with_domain:
        return f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}{path}"
        # return f"{settings.APP_SCHEME}://discu.eu{path}"
    else:
        return path


def discussions_canonical_url(q, with_domain=True):
    if not q:
        q = ""
    q = q.lower()

    cu = cleanurl.cleanurl(q)

    if cu.scheme in ("http", "https"):
        q = cu.url or ""
        q = q.replace("http://", "https://")

    return discussions_url(q, with_domain)


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def __noop(a):
    return a


def most_similar(bs, a, key=__noop):
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


def url_root(url):
    """Return the *root* of the page"""

    if type(url) is str:
        url = cleanurl.cleanurl(
            url, generic=True, respect_semantics=True, host_remap=False
        )

    if url.hostname in (
        "www.github.com",
        "github.com",
        "gitlab.com",
        "www.gitlab.com",
    ):
        parts = (url.path or "").split("/")
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return url.hostname + "/" + parts[0]

    if url.hostname in (
        "www.twitter.com",
        "twitter.com",
        "mobile.twitter.com",
    ):
        parts = (url.path or "").split("/")
        parts = [p for p in parts if p]
        if len(parts) >= 3 and parts[1] == "status":
            return url.hostname + "/" + parts[0]

    if url.hostname in (
        "mastodon.social",
        "mastodon.technology",
    ):
        parts = (url.path or "").split("/")
        parts = [p for p in parts if p]
        if len(parts) >= 3 and parts[0] == "web" and parts[1][0] == "@":
            return url.hostname + "/web/" + parts[1]

    return url.hostname
