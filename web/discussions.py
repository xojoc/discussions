import re
import urllib.parse as url_parse
from enum import Enum

import django
import requests
import urllib3
from django_redis import get_redis_connection
from urllib3.util import Url

from web import models


class PreferredExternalURL(Enum):
    Standard = 1
    Mobile = 2
    Old = 3


# todo:
#   doi (https://www.tandfonline.com/doi/abs/10.1080/03085147.2019.1678262)
#   rel=canonical

# fixme: non permanent redirects?

def _follow_redirects(url, client, redis, cache, timeout):
    if cache:
        key_prefix = "discussions:comments:redirect:"
        key_prefix_skip = "discussions:comments:skip_redirect:"

        if redis.get(key_prefix_skip + url):
            return url

        final_url = redis.get(key_prefix + url)
        if final_url:
            return final_url.decode()

    try:
        # xojoc: not all websites support the HEAD method. Use GET for now
        r = client.get(url, allow_redirects=True, timeout=timeout)
    except Exception:
        if cache:
            redis.set(key_prefix_skip + url, 1, ex=60 * 60 * 6)
        return url

    if r.status_code != 200:
        if cache:
            redis.set(key_prefix_skip + url, 1, ex=60 * 60 * 24 * 15)
        return url

    final_url = r.url
    if not final_url:
        if cache:
            redis.set(key_prefix_skip + url, 1, ex=60 * 60 * 6)
        return url

    if cache:
        redis.set(key_prefix + url, final_url, ex=60 * 60 * 6)

    return final_url


def _canonical_host(host):
    if not host:
        return ''

    for prefix in ['www.', 'ww2.', 'm.', 'mobile.']:
        if host.startswith(prefix) and len(host) > (len(prefix) + 1):
            host = host[len(prefix):]

    return host


def _canonical_path(path):
    if not path:
        return ''

    path = re.sub('/+', '/', path)

    suffixes = ['/default', '/index',
                '.htm', '.html', '.shtml',
                '.php', '.jsp', '.aspx',
                '.cms', '.md',
                '.pdf', '.stm',
                '/']
    found_suffix = True
    while found_suffix:
        found_suffix = False
        for suffix in suffixes:
            if path.endswith(suffix):
                path = path[:-len(suffix)]
                found_suffix = True

    return path


def _canonical_query(query):
    pq = url_parse.parse_qsl(query, keep_blank_values=True)

    queries_to_skip = {'cd-origin',
                       'utm_term', 'utm_campaign', 'utm_content', 'utm_source', 'utm_medium',
                       'gclid', 'gclsrc', 'dclid', 'fbclid', 'zanpid',
                       'guccounter', 'campaign_id',
                       'tstart'}

    return sorted([q for q in pq if q[0] not in queries_to_skip])


def _fragment_to_path(host, path, fragment):
    if not fragment:
        return None

    new_path = None

    if (
            path == '' and
            fragment.startswith('!')
    ):

        new_path = fragment[1:]
        if not new_path.startswith('/'):
            new_path = '/' + new_path

    if (
            host == 'cnn.com' and
            path == '/video' and
            fragment.startswith('/')
    ):
        new_path = fragment

    if (
            host == 'groups.google.com' and
            path.startswith('/forum') and
            fragment.startswith('!topic/')
    ):
        new_path = "/g/" + fragment[len('!topic/'):].replace("/", "/c/", 1)

    return new_path


def _canonical_webarchive(host, path, parsed_query):
    web_archive_prefix = '/web/'
    if host == 'web.archive.org':
        if path.startswith(web_archive_prefix):
            parts = path[len(web_archive_prefix):].split('/', 1)
            if len(parts) == 2 and parts[1].startswith(('http:/', 'https:/')):
                try:
                    url = parts[1]
                    url = url.replace("http:/", "http://", 1)
                    url = url.replace("https:/", "https://", 1)
                    u = urllib3.util.parse_url(canonical_url(url))
                    host = u.host
                    path = u.path
                    parsed_query = u.query
                except Exception:
                    pass

    return host, path, parsed_query


def _canonical_youtube(host, path, parsed_query):
    if host == 'youtube.com':
        if path == '/watch':
            for v in parsed_query:
                if v[0] == 'v':
                    host = 'youtu.be'
                    path = '/' + v[1]
                    parsed_query = None
                    break

        if path.startswith("/embed/"):
            path_parts = path.split('/')
            if len(path_parts) >= 3 and path_parts[-1] != '':
                host = 'youtu.be'
                path = '/' + path_parts[-1]
                parsed_query = None

    return host, path, parsed_query


def _canonical_medium(host, path, parsed_query):
    if host == 'medium.com':
        path_parts = path.split('/')
        if len(path_parts) >= 3:
            path = '/p/' + path_parts[-1].split('-')[-1]
    if host.endswith('.medium.com'):
        path_parts = path.split('/')
        if len(path_parts) >= 2:
            path = '/' + path_parts[-1].split('-')[-1]

    return host, path, parsed_query


def _canonical_github(host, path, parsed_query):
    if host == 'github.com':
        path = path.removesuffix('/tree/master')

    return host, path, parsed_query


def _canonical_nytimes(host, path, parsed_query):
    if host == 'nytimes.com':
        parsed_query = None
    if host == 'open.nytimes.com':
        parsed_query = None
        path_parts = path.split('/')
        if len(path_parts) >= 2:
            path = '/' + path_parts[-1].split('-')[-1]

    return host, path, parsed_query


def _canonical_techcrunch(host, path, parsed_query):
    if host == 'techcrunch.com' or host.endswith('.techcrunch.com'):
        parsed_query = None

    return host, path, parsed_query


def _canonical_wikipedia(host, path, parsed_query):
    if host.endswith('.wikipedia.org'):
        parsed_query = None

    return host, path, parsed_query


def _canonical_arstechnica(host, path, parsed_query):
    if host == 'arstechnica' and 'viewtopic.php' not in path:
        parsed_query = None

    return host, path, parsed_query


def _canonical_bbc(host, path, parsed_query):
    if host == 'news.bbc.co.uk':
        parsed_query = None

    return host, path, parsed_query


def _canonical_specific_websites(host, path, parsed_query):
    for h in [_canonical_webarchive,
              _canonical_youtube,
              _canonical_medium,
              _canonical_github,
              _canonical_nytimes,
              _canonical_techcrunch,
              _canonical_wikipedia,
              _canonical_arstechnica,
              _canonical_bbc]:
        host, path, parsed_query = h(host, path, parsed_query)
    return host, path, parsed_query


def canonical_url(url, client=None, redis=None, follow_redirects=False, cache=True, timeout=3.05):
    if not url:
        return url

    if follow_redirects:
        if not client:
            client = requests
        if not redis:
            redis = get_redis_connection("default")
        url = _follow_redirects(url, client, redis, cache, timeout)

    try:
        u = urllib3.util.parse_url(url)
    except Exception:
        return url

    host = _canonical_host(u.host)
    path = _canonical_path(u.path)
    parsed_query = _canonical_query(u.query)

    new_path = _fragment_to_path(host, path, u.fragment)
    if new_path is not None:
        path = new_path

    host, path, parsed_query = _canonical_specific_websites(host, path, parsed_query)

    query = url_parse.urlencode(parsed_query or '')

    if query:
        return f"{host}{path}?{query}"
    else:
        return f"{host}{path}"


def split_scheme(url):
    url = url.lower()

    if not url:
        return "", url

    try:
        u = urllib3.util.parse_url(url)
    except Exception:
        return "", url

    scheme = u.scheme

    u = Url(
        scheme=None,
        auth=u.auth,
        host=u.host,
        port=u.port,
        path=u.path,
        query=u.query,
        fragment=u.fragment)

    return scheme, u.url


def update_all_canonical_urls(manual_commit=True):
    # c = http.client(with_retries=False)
    # r = get_redis_connection("default")

    if manual_commit:
        previous_autocommit = django.db.transaction.get_autocommit()
        django.db.transaction.set_autocommit(False)

    stories = models.Discussion.objects.all()
    for story in stories:
        dirty = False

        cu = canonical_url(story.story_url)
        if cu == story.schemeless_story_url:
            story.canonical_story_url = None
            dirty = True
        elif len(cu) <= 2000:
            story.canonical_story_url = cu
            dirty = True

        print("a")
        # if random.random() <= 0.001:
        #     rcu = canonical_url(story.story_url,
        #                         follow_redirects=True,
        #                         client=c,
        #                         redis=r,
        #                         cache=False)
        #     if rcu == story.schemeless_story_url or rcu == story.canonical_story_url:
        #         story.canonical_redirect_url = None
        #         dirty = True
        #     elif len(rcu) <= 2000:
        #         story.canonical_redirect_url = rcu
        #         dirty = True

        if dirty:
            story.save()

    if manual_commit:
        django.db.transaction.commit()
        django.db.transaction.set_autocommit(previous_autocommit)
