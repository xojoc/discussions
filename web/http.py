from django.conf import settings
from django_redis import get_redis_connection
import requests
import cachecontrol
from cachecontrol import CacheControl
from cachecontrol.cache import BaseCache
import datetime
import time
import urllib3
from bs4 import BeautifulSoup


class _CustomRedisCache(BaseCache):
    def __init__(self, conn):
        self.conn = conn
        self.prefix = 'discussions:http_cache:'

    def set(self, key, value, expires=None):
        if not expires:
            self.conn.setex(self.prefix + key, 60 * 60 * 24 * 5, value)
        else:
            expires = expires - datetime.utcnow()
            self.conn.setex(self.prefix + key, int(expires.total_seconds()),
                            value)

    def get(self, key):
        return self.conn.get(self.prefix + key)

    def delete(self, key):
        self.conn.delete(self.prefix + key)

    def clear(self):
        for key in self.conn.keys(self.prefix + '*'):
            self.conn.delete(key)


def _default_headers():
    headers = requests.utils.default_headers()
    headers['User-Agent'] = settings.USERAGENT
    return headers


def client(with_cache=False, with_retries=True):
    r = get_redis_connection("default")

    retries = urllib3.Retry(total=4,
                            connect=3,
                            read=3,
                            status=3,
                            backoff_factor=0.6,
                            redirect=15,
                            raise_on_redirect=False,
                            raise_on_status=False,
                            status_forcelist=set([429, 500, 502, 504]))

    session = requests.session()
    session.headers = _default_headers()
    session

    client = session

    if with_cache:
        client = CacheControl(session,
                              cache=_CustomRedisCache(r),
                              cache_etags=True)

    if with_retries:
        client.get_adapter('http://').max_retries = retries
        client.get_adapter('https://').max_retries = retries

    return client


def _rate_limit(r, host):
    if r.get('discussions:rate_limit:' + host):
        time.sleep(2)
        return _rate_limit(host)
    r.set('discussions:rate_limit:' + host, 1, ex=3)


def fetch(url, force_cache=0, refresh_on_get=False, rate_limiting=True):
    url = cachecontrol.CacheController.cache_url(url)
    request = requests.Request(method='GET',
                               url=url,
                               headers=_default_headers(),
                               hooks=requests.hooks.default_hooks())
    r = get_redis_connection("default")
    c = client()
    adapter = c.get_adapter(url=request.url)
    if force_cache:
        serialized_resp = r.get('discussions:forced_cached:' + url)
        resp = adapter.controller.serializer.loads(request, serialized_resp)
        if resp:
            if refresh_on_get:
                r.expire('discussions:forced_cached:' + url, force_cache)
            return adapter.build_response(request, resp, from_cache=True)
    resp = adapter.controller.cached_request(request)
    if resp:
        redirect_to = resp.get_redirect_location()
        if redirect_to:
            return fetch(redirect_to,
                         force_cache=force_cache,
                         rate_limiting=rate_limiting)
        return adapter.build_response(request, resp, from_cache=True)

    if rate_limiting:
        _rate_limit(r, urllib3.util.parse_url(url).host)
    resp = c.send(request.prepare(), stream=True)

    if force_cache:
        serialized = adapter.controller.serializer.dumps(request, resp.raw)
        r.set('discussions:forced_cached:' + url, serialized, ex=force_cache)
        return fetch(url, force_cache=force_cache, rate_limiting=rate_limiting)

    return resp


def parse_html(res, safe_html=False):
    h = BeautifulSoup(res.content, 'lxml')
    if safe_html:
        if h.script:
            h.script.decompose()
        if h.form:
            h.form.decompose()
        if h.iframe:
            h.iframe.decompose()
        if h.frameset:
            h.frameset.decompose()
    return h
