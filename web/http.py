# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
import time

import bs4
import cachecontrol
import minify_html
import requests
import requests.utils as requests_utils
import urllib3
from bs4 import BeautifulSoup
from cachecontrol import CacheControl
from cachecontrol.cache import BaseCache
from django.conf import settings
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)


class _CustomRedisCache(BaseCache):
    def __init__(self, conn):
        self.conn = conn
        self.prefix = "discussions:http_cache:"

    def set(self, key, value, expires=None):
        if not expires:
            self.conn.setex(self.prefix + key, 60 * 60 * 24 * 5, value)
        else:
            expires = max(expires, 60 * 60 * 24 * 5)
            self.conn.setex(self.prefix + key, expires, value)

    def get(self, key):
        return self.conn.get(self.prefix + key)

    def delete(self, key):
        self.conn.delete(self.prefix + key)

    def clear(self):
        for key in self.conn.keys(self.prefix + "*"):
            self.conn.delete(key)


def _default_headers():
    headers = requests.utils.default_headers()
    headers["User-Agent"] = settings.USERAGENT
    return headers


def client(with_cache=False, with_retries=True):
    r = get_redis_connection("default")

    retries = urllib3.Retry(
        total=4,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.6,
        redirect=15,
        raise_on_redirect=False,
        raise_on_status=False,
        status_forcelist={429, 500, 502, 504},
    )

    session = requests.session()
    session.headers = _default_headers()

    client = session

    if with_cache:
        client = CacheControl(
            session,
            cache=_CustomRedisCache(r),
            cache_etags=True,
        )

    if with_retries:
        client.get_adapter("http://").max_retries = retries
        client.get_adapter("https://").max_retries = retries

    return client


def _rate_limit(r, host):
    if r.get("discussions:rate_limit:" + host):
        time.sleep(2)
        return _rate_limit(r, host)
    r.set("discussions:rate_limit:" + host, 1, ex=3)
    return None


def fetch(
    url,
    force_cache=0,
    refresh_on_get=False,
    rate_limiting=True,
    timeout=30,
    with_retries=True,
    with_cache=False,
) -> requests.Response | None:
    url = cachecontrol.CacheController.cache_url(url)
    request = requests.Request(
        method="GET",
        url=url,
        headers=_default_headers(),
        hooks=requests.hooks.default_hooks(),
    )
    c = client(with_retries=with_retries, with_cache=with_cache)

    resp = None
    try:
        resp = c.send(request.prepare(), stream=True, timeout=timeout)
    except requests.exceptions.RequestException:
        logger.warning("http.fetch: send fail", exc_info=True)

    return resp


def parse_html(
    res: str | bytes | requests.Response,
    *,
    safe_html: bool = False,
    clean: bool = False,
) -> BeautifulSoup | None:
    html = None

    html = res if isinstance(res, bytes | str) else (res.text or "")

    if not html:
        return None

    if clean:
        safe_html = True

    if clean:
        try:
            html = minify_html.minify(
                html,
                minify_js=False,
                minify_css=False,  # TODO: reenable when https://github.com/Mnwa/css-minify/issues/9 if fixed
                ensure_spec_compliant_unquoted_attribute_values=True,
                keep_spaces_between_attributes=True,
                remove_processing_instructions=True,
            )
        except BaseException:  # noqa: BLE001
            logger.info(
                "minify_html failed: resource: {res.pk}",
                exc_info=True,
            )

    h = BeautifulSoup(html, "lxml")
    if safe_html:
        while h.script:
            h.script.decompose()
        while h.form:
            h.form.decompose()
        while h.iframe:
            h.iframe.decompose()
        while h.frameset:
            h.frameset.decompose()

    if clean:
        while h.style:
            h.style.decompose()
        while h.svg:
            h.svg.decompose()
        while h.link:
            h.link.decompose()
        comments = h.findAll(text=lambda text: isinstance(text, bs4.Comment))
        for comment in comments:
            comment.extract()

    return h
