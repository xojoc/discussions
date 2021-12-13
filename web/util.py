from urllib.parse import quote
from difflib import SequenceMatcher
from discussions import settings


def discussions_url(q, with_domain=True):
    path = '/q/' + quote(q, safe='/:?&=')
    if with_domain:
        return f'https://{settings.APP_DOMAIN}{path}'
    else:
        return path


def discussions_canonical_url(q, with_domain=True):
    path = '/?q=' + quote(q)
    if with_domain:
        return f'https://{settings.APP_DOMAIN}{path}'
    else:
        return path


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def __noop(a):
    return a


def most_similar(bs, a, key=__noop):
    if not bs:
        return None
    return max({(similarity(a, key(b)), b) for b in bs}, key=lambda x: x[0])[1]
