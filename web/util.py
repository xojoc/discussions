from urllib.parse import quote
from difflib import SequenceMatcher
from discussions import settings
from . import discussions
import os


def discussions_url(q, with_domain=True):
    if not q:
        q = ''
    path = '/q/' + quote(q, safe='/:?&=')
    if with_domain:
        return f'https://{settings.APP_DOMAIN}{path}'
    else:
        return path


def discussions_canonical_url(q, with_domain=True):
    if not q:
        q = ''
    q = q.lower()
    scheme, url = discussions.split_scheme(q)
    if scheme in ('http', 'https'):
        cu = discussions.canonical_url(url)
        q = f"{scheme}://{cu}"

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
    return os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true'
