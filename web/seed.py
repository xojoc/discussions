# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
import re
import time

import feedparser

from web import crawler, extract, http

logger = logging.getLogger(__name__)


def this_week_in_rust():
    start_url = "https://this-week-in-rust.org/blog/archives/index.html"

    r = crawler.fetch(start_url)
    if not r:
        logger.debug("this week in rust not fetched")
        return

    html = http.parse_html(r.clean_html, safe_html=True)

    links = html.select("a") or []
    logger.debug(f"len {len(links)}")
    for link in links:
        href = link.get("href")
        if not href:
            continue

        if not re.search(
            r"this-week-in-rust.org/blog/\d\d\d\d/\d\d/\d\d/",
            href,
        ):
            logger.debug(f"not matching {href}")
            continue

        c = 0
        r = crawler.fetch(href)
        if r:
            h = http.parse_html(r.clean_html, safe_html=True)
            hs = extract.structure(h, href)
            for link in hs.outbound_links:
                if not link.get("href"):
                    continue
                crawler.add_to_queue(link.get("href"), priority=3)
                c += 1

        logger.debug(f"this week in rust: {c} from {href}")
        time.sleep(5)


def feed_to_queue(feed):
    f = feedparser.parse(feed)
    for e in f["entries"]:
        crawler.add_to_queue(e["link"])


def all():
    feed_to_queue("https://blog.rust-lang.org/feed.xml")
    feed_to_queue("https://blog.rust-lang.org/inside-rust/feed.xml")
    feed_to_queue("https://andrewkelley.me/rss.xml")
    feed_to_queue("https://planet.gnome.org/atom.xml")
    # https://zigmonthly.org/letters/2021/october/
