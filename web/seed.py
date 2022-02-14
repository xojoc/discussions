from web import crawler, http, extract
import logging
import re
import time


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
            r"this-week-in-rust.org/blog/\d\d\d\d/\d\d/\d\d/", href
        ):
            logger.debug(f"not matching {href}")
            continue

        c = 0
        r = crawler.fetch(href)
        if r:
            h = http.parse_html(r.clean_html, safe_html=True)
            hs = extract.structure(h)
            for link in hs.outbound_links:
                if not link.get("href"):
                    continue
                crawler.add_to_queue(link.get("href"), priority=3)
                c += 1

        logger.debug(f"this week in rust: {c} from {href}")
        time.sleep(5)


def all():
    this_week_in_rust()
    # https://zigmonthly.org/letters/2021/october/
