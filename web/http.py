# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
import time

import bs4
import cachecontrol
import minify_html
import requests
import requests.hooks
import requests.utils
import urllib3
from bs4 import BeautifulSoup
from cachecontrol import CacheControl
from cachecontrol.cache import BaseCache
from django.conf import settings
from django_redis import get_redis_connection
from typing_extensions import override

logger = logging.getLogger(__name__)


class _CustomRedisCache(BaseCache):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.prefix = "discussions:http_cache:"

    @override
    def set(self, key, value, expires=None):
        if not expires:
            self.conn.setex(self.prefix + key, 60 * 60 * 24 * 5, value)
        else:
            expires = max(expires, 60 * 60 * 24 * 5)
            self.conn.setex(self.prefix + key, expires, value)

    @override
    def get(self, key):
        return self.conn.get(self.prefix + key)

    @override
    def delete(self, key):
        self.conn.delete(self.prefix + key)

    def clear(self):
        for key in self.conn.keys(self.prefix + "*"):
            self.conn.delete(key)


def _default_headers():
    headers = requests.utils.default_headers()
    headers["User-Agent"] = settings.USERAGENT
    return headers


def client(*, with_cache=False, with_retries=True):
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
    url: str,
    *,
    timeout: int = 30,
    with_retries: bool = True,
    with_cache: bool = False,
) -> requests.Response | None:
    try:
        url = cachecontrol.CacheController.cache_url(url)
    except Exception:  # noqa: BLE001
        # cache_url raises Exception if url is not absolute
        return None
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
        logger.warning("http.fetch: send fail: %s", url)

    return resp


def parse_html(
    res: str | bytes | requests.Response,
    *,
    safe_html: bool = False,
    clean: bool = False,
    url: str = "",
) -> BeautifulSoup | None:
    try:
        html = res if isinstance(res, bytes | str) else (res.text or "")
    except requests.exceptions.RequestException:
        html = None

    if not html:
        return None

    u = None
    if url:
        try:
            u = urllib3.util.parse_url(url)
        except ValueError:
            u = None

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
        while h.canvas:
            h.canvas.decompose()
        while h.template:
            h.template.decompose()
        while h.link:
            h.link.decompose()

        for t in h.find_all("include-fragment"):
            t.decompose()

        for comment in h.findAll(
            text=lambda text: isinstance(text, bs4.Comment),
        ):
            comment.extract()

        attribute_prefixes_to_remove = (
            "data-",
            "darker-",
            "typography",
            "system-icons",
        )
        for tag in h.find_all(
            lambda t: any(
                i.startswith(attribute_prefixes_to_remove) for i in t.attrs
            ),
        ):
            for attr in list(tag.attrs):
                if attr.startswith(attribute_prefixes_to_remove):
                    del tag.attrs[attr]

        for t in h.select(
            'meta[name="optimizely-datafile"], '
            'meta[name="viewport"], '
            'meta[name="theme-color"], '
            'meta[name="color-scheme"], '
            'meta[http-equiv="origin-trial"], '
            'meta[http-equiv="X-UA-Compatible"], '
            'meta[property="og:video:tag"], '
            'meta[property="al:ios:url"], '
            'meta[property="al:android:url"], '
            'meta[property="al:web:url"], '
            'meta[property="og:url"], '
            # 'meta[property^="al:android:"], '
            # 'meta[property^="al:ios:"], '
            # 'meta[property^="al:web:"], '
            'meta[name$="-verification"], '
            "#adblock-test",
        ):
            t.decompose()

        if u and u.host in {"twitter.com", "www.twitter.com", "m.twitter.com"}:
            # the body doesn't contain much, everything is inside the meta tags
            if h.body:
                h.body.decompose()

        if u and u.host in {"www.youtube.com", "youtube.com", "youtu.be"}:
            # the body doesn't contain much, everything is inside the meta tags
            if h.body:
                h.body.decompose()

        if u and u.host in {"www.reddit.com", "reddit.com", "old.reddit.com"}:
            # the body doesn't contain much, everything is inside the meta tags
            if h.body:
                h.body.decompose()

        if u and u.host in {"streamable.com", "www.streamable.com"}:
            # the body doesn't contain much, everything is inside the meta tags
            if h.body:
                h.body.decompose()

    return h
