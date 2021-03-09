import logging
import datetime
import time

from django.utils.timezone import make_aware
from django.utils import timezone
import datetime
from django_redis import get_redis_connection

from web import http, models, discussions

logger = logging.getLogger(__name__)


def fetch_discussions(from_id, to_id, fetching_all=False):
    redis = get_redis_connection("default")
    r_skip_set = "discussions:hn:skip_set"
    c = http.client(with_cache=False)

    cache_timeout = 60 * 60 * 24

    # If nothing changes since last fetch, then we skip
    # this item for a while
    nothing_changed_cache_timeout = 60 * 60 * 24 * 7

    for id in range(from_id, to_id):
        if redis.sismember(r_skip_set, id):
            continue

        try:
            item = c.get(
                f"https://hacker-news.firebaseio.com/v0/item/{id}.json",
                timeout=3.05).json()
        except Exception as e:
            logger.error(f"fetch_hn_stories: {e}")
            time.sleep(2)
            continue

        if not item:
            continue

        platform_id = f"h{id}"

        if item.get('kids'):
            for kid in item.get('kids'):
                redis.sadd(r_skip_set, kid)

        if item.get('deleted'):
            redis.sadd(r_skip_set, id)
            models.Discussion.objects.filter(pk=platform_id).delete()
            continue

        if item.get('type') != 'story':
            redis.sadd(r_skip_set, id)
            continue

        if not item.get('url'):
            redis.sadd(r_skip_set, id)
            continue

        if item.get('dead'):
            redis.sadd(r_skip_set, id)
            models.Discussion.objects.filter(pk=platform_id).delete()
            continue

        if not item.get('time'):
            logger.info(f"HN no time: {item}")
            continue

        if not item.get('descendants'):
            continue

        if item.get('score') < 0:
            continue

        created_at = datetime.datetime.fromtimestamp(item.get('time'))

        scheme, url = discussions.split_scheme(item.get('url'))
        if len(url) > 2000:
            continue
        if not scheme:
            logger.warn(f"HN: no scheme for {platform_id}, url {item.get('url')}")
            continue

        canonical_url = discussions.canonical_url(url)

        try:
            discussion = models.Discussion.objects.get(
                pk=platform_id)

            one_week_ago = timezone.now() - datetime.timedelta(days=7 * 1)

            #if (discussion.comment_count == item.get('descendants') and
            #    discussion.score == item.get('score') and
            #    discussion.created_at < one_week_ago):

            #    # Comment count and score didn't change, skip this item for a while
            #    ### redis.set(r_skip_prefix + str(id), 1, ex=nothing_changed_cache_timeout)

            discussion.comment_count = item.get('descendants') or 0
            discussion.score = item.get('score') or 0
            discussion.created_at = make_aware(created_at)
            discussion.scheme_of_story_url = scheme
            discussion.schemeless_story_url = url
            discussion.canonical_story_url = canonical_url
            discussion.title = item.get('title')
            discussion.save()
        except models.Discussion.DoesNotExist:
            models.Discussion(
                platform_id=platform_id,
                comment_count=item.get('descendants') or 0,
                score=item.get('score') or 0,
                created_at=make_aware(created_at),
                scheme_of_story_url=scheme,
                schemeless_story_url=url,
                canonical_story_url=canonical_url,
                title=item.get('title')).save()
