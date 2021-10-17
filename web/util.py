from urllib.parse import quote as quote_url
from difflib import SequenceMatcher


def discussions_url(story_url):
    return 'https://discussions.xojoc.pw/?url=' + quote_url(story_url)


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def __noop(a):
    return a


def most_similar(bs, a, key=__noop):
    if not bs:
        return None
    return max({(similarity(a, key(b)), b) for b in bs}, key=lambda x: x[0])[1]
