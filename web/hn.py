import logging
from django.utils.timezone import make_aware
import datetime
from django_redis import get_redis_connection
from web import http, models, discussions

logger = logging.getLogger(__name__)

def fetch_discussions(from_id, to_id, fetching_all=False):
    c = http.client(with_cache=False)
    redis = get_redis_connection("default")
    r_skip_prefix = "discussions:hn:skip:"
    skip_timeout = 60*60
    r_revisit_set = "discussions:hn:revisit_set"
    r_revisit_max_id = "discussions:hn:revisit_max_id"

    revisit_max_id = int(redis.get(r_revisit_max_id) or -1)

    for id in range(from_id, to_id):
        if (id < revisit_max_id and
            (not redis.sismember(r_revisit_set, id))):
            continue

        if redis.exists(r_skip_prefix + str(id)):
            continue

        # xojoc: if this fails, we let the whole task fail so it gets relaunched
        #        with the same parameters
        item = c.get(
            f"https://hacker-news.firebaseio.com/v0/item/{id}.json",
            timeout=3.05).json()

        if not item:
            continue

        platform_id = f"h{id}"

        for kid in item.get('kids', []):
            redis.setex(r_skip_prefix + str(kid), skip_timeout, 1)

        if item.get('deleted'):
            models.Discussion.objects.filter(pk=platform_id).delete()
            continue

        if item.get('type') != 'story':
            continue

        if not item.get('url'):
            continue

        if item.get('dead'):
            models.Discussion.objects.filter(pk=platform_id).delete()
            continue

        redis.sadd(r_revisit_set, id)

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

    redis.set(r_revisit_max_id, to_id)
