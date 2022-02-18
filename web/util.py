from urllib.parse import quote
from difflib import SequenceMatcher
from discussions import settings
import os
import cleanurl


def discussions_url(q, with_domain=True):
    if not q:
        q = ""
    path = "/q/" + quote(q, safe="/:?&=")
    if with_domain:
        return f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}{path}"
    else:
        return path


def discussions_canonical_url(q, with_domain=True):
    if not q:
        q = ""
    q = q.lower()

    cu = cleanurl.cleanurl(q)

    if cu.scheme in ("http", "https"):
        q = cu.url

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
