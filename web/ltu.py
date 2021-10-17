import datetime
import logging
import time
import re
from celery import shared_task
from discussions.settings import APP_CELERY_TASK_MAX_TIME
from web import http, discussions, models
from web import celery_util
from django_redis import get_redis_connection
from web import util
from django.utils.timezone import make_aware

logger = logging.getLogger(__name__)

# http://lambda-the-ultimate.org/node?from=0


class EndOfPages(Exception):
    pass


def __exclude_story_url(a):
    if not a:
        return False
    href = a.get('href')
    if not href:
        return False

    href = href.removeprefix("https://")
    href = href.removeprefix("http://")

    if not href:
        return False

    return not (href.startswith('duckduckgo.') or href.startswith('google.')
                or href.startswith('lambda-the-ultimate.'))


@shared_task(ignore_result=True)
def process_item(item, platform_prefix):
    # breakpoint()

    try:
        slug = item.select_one('.title a').get('href').strip()
    except Exception:
        slug = None

    platform_id = f"{platform_prefix}{slug}"

    title = item.select_one('.title').get_text().strip()

    comment_count = 0
    score = 0

    for link in item.select('.links a'):
        if not comment_count:
            try:
                comment_count = re.match(
                    r'(\d+) comment',
                    link.get_text().strip().lower()).group(1)
                comment_count = int(comment_count)
            except Exception:
                comment_count = 0

    try:
        score = re.match(
            r'.* (\d+) reads',
            item.select_one('.links').get_text().strip().lower()).group(1)
        score = int(score)
    except Exception:
        score = 0

    body_links = item.select('.content a')

    if not body_links or len(body_links) == 0:
        return

    body_links = list(filter(__exclude_story_url, body_links))

    if not body_links or len(body_links) == 0:
        logger.warn(f"LTU: no links after filter {platform_id}")
        return

    if len(body_links) == 1:
        story_url = body_links[0].get('href')

    if len(body_links) > 1:
        story_url = util.most_similar(body_links,
                                      title,
                                      key=lambda x: x.get_text())
        story_url = story_url.get('href')

    if not story_url:
        return

    try:
        created_at = re.match(r'.* at (\d\d\d\d-\d\d-\d\d \d\d:\d\d)',
                              item.select_one('.links').get_text()).group(1)

        created_at = datetime.datetime.fromisoformat(created_at)
        created_at = make_aware(created_at)
    except Exception:
        created_at = None

    try:
        tags = map(lambda x: x.get_text().strip(),
                   item.select('.links a[href^="taxonomy/"]'))
        tags = list(tags)
    except Exception:
        tags = []

    scheme, url = discussions.split_scheme(story_url)
    if len(url) > 2000:
        return
    if not scheme:
        return

    canonical_url = discussions.canonical_url(url)
    if len(canonical_url) > 2000 or canonical_url == url:
        canonical_url = None

    try:
        discussion = models.Discussion.objects.get(pk=platform_id)

        discussion.comment_count = comment_count
        discussion.score = score
        discussion.created_at = created_at
        discussion.scheme_of_story_url = scheme
        discussion.schemeless_story_url = url
        discussion.canonical_story_url = canonical_url
        discussion.title = title
        discussion.tags = tags
        discussion.save()
    except models.Discussion.DoesNotExist:
        models.Discussion(platform_id=platform_id,
                          comment_count=comment_count,
                          score=score,
                          created_at=created_at,
                          scheme_of_story_url=scheme,
                          schemeless_story_url=url,
                          canonical_story_url=canonical_url,
                          title=title,
                          tags=tags).save()


def fetch_discussions(current_page, platform_prefix, base_url):
    c = http.client(with_cache=False)

    start_time = time.monotonic()

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        page_url = f"{base_url}/node?from={current_page*10}"

        r = c.get(page_url, timeout=11.05)

        h = http.parse_html(r)

        body = h.get_text().lower().strip()
        body = ' '.join(body.split())

        if r.status_code == 404 or \
           body.find('welcome to your new drupal-powered') >= 0:
            raise EndOfPages

        for item in h.find_all('div', 'node'):
            process_item(item, platform_prefix)

        current_page += 1

        time.sleep(2.1)

    return current_page


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_all_ltu_discussions():
    r = get_redis_connection("default")
    redis_prefix = 'discussions:ltu:fetch_all_discussions:'
    current_index = r.get(redis_prefix + 'current_index')
    max_index = int(r.get(redis_prefix + 'max_index') or 0)
    if current_index is None or not max_index or (int(current_index) >
                                                  max_index):
        max_index = 1_000_000_000
        r.set(redis_prefix + 'max_index', max_index)
        current_index = 0

    current_index = int(current_index)

    try:
        current_index = fetch_discussions(current_index, 'u',
                                          'http://lambda-the-ultimate.org')
    except EndOfPages:
        current_index = max_index + 1

    r.set(redis_prefix + 'current_index', current_index)
