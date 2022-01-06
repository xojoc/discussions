from web import util, archiveis
import os
import logging
from django.utils.timezone import make_aware
import datetime
from django_redis import get_redis_connection
from web import http, models, discussions
from celery import shared_task
import time
from web import celery_util, worker
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache

logger = logging.getLogger(__name__)

cache_prefix = 'discussions:hn:'


def __cache_skip_prefix(platform):
    return f"discussions:hn:{platform}:skip:"


def __redis_comment_set_key(platform):
    return f"discussions:hn:{platform}:comment_set"


def __base_url(platform):
    if platform == 'h':
        return 'https://hacker-news.firebaseio.com'
    elif platform == 'a':
        return 'https://laarrc.firebaseio.com'


def process_item(platform, item, redis=None, skip_timeout=None):
    if not item:
        return

    if not redis:
        redis = get_redis_connection("default")

    platform_id = f"{platform}{item.get('id')}"

    for kid in item.get('kids', []):
        redis.sadd(__redis_comment_set_key(platform), kid)

    if item.get('deleted'):
        models.Discussion.objects.filter(pk=platform_id).delete()
        return

    if item.get('type') != 'story':
        if item.get('type') == 'comment':
            redis.sadd(__redis_comment_set_key(platform), item.get('id'))
        else:
            logger.debug(f"{platform_id}: item not story or comment: {item.get('type')}")
        return

    if item.get('dead'):
        models.Discussion.objects.filter(pk=platform_id).delete()
        return

    if item.get('time'):
        created_at = datetime.datetime.fromtimestamp(item.get('time'))
        created_at = make_aware(created_at)
    else:
        created_at = None

    scheme, url, canonical_url = None, None, None

    if item.get('url'):
        scheme, url = discussions.split_scheme(item.get('url'))
        canonical_url = discussions.canonical_url(url)

    models.Discussion.objects.update_or_create(
        pk=platform_id,
        defaults={'comment_count': item.get('descendants') or 0,
                  'score': item.get('score') or 0,
                  'created_at': created_at,
                  'scheme_of_story_url': scheme,
                  'schemeless_story_url': url,
                  'canonical_story_url': canonical_url,
                  'title': item.get('title')})

    if skip_timeout:
        cache.set(__cache_skip_prefix(platform) + str(item.get('id')), 1, timeout=skip_timeout)


def fetch_item(platform, id, client=None):
    if not client:
        client = http.client(with_cache=False)

    if cache.get(__cache_skip_prefix(platform) + str(id)):
        return

    bu = __base_url(platform)

    try:
        return client.get(f"{bu}/v0/item/{id}.json",
                          timeout=11.05).json()
    except Exception as e:
        time.sleep(3)
        logger.warn(f'fetch_item: {e}')
        return


def _worker_fetch(self, platform):
    client = http.client(with_cache=False)
    redis = get_redis_connection()

    cache_current_item_key = f'discussions:hn:{platform}:current_item'

    current_item = cache.get(cache_current_item_key) or 1
    current_item = int(current_item)
    max_item = None

    bu = __base_url(platform)

    while True:
        if worker.graceful_exit(self):
            logger.info("hn fetch: graceful exit")
            break

        if not max_item:
            max_item = client.get(f"{bu}/v0/maxitem.json").content
            max_item = int(max_item)

        if current_item > max_item:
            current_item = 1

        queue = []

        c = 0
        while True:
            if not redis.sismember(__redis_comment_set_key(platform), current_item):
                queue.append((current_item, 0))
                c += 1

            current_item += 1

            if current_item > max_item:
                break

            if c > 70:
                break

        # updates = client.get(f"{bu}/v0/updates.json",
        #                 timeout=7.05).json()

        # for id in updates.get('items')[:10]:
        #     queue.append((id, 60*15))

        for id in client.get(f"{bu}/v0/topstories.json",
                             timeout=7.05).json()[:30]:
            queue.append((id, 60*15))

        # for id in client.get(f"{bu}/v0/beststories.json",
        #                      timeout=7.05).json()[:20]:
        #     queue.append((id, 60*15))

        for id in client.get(f"{bu}/v0/newstories.json",
                             timeout=7.05).json()[:20]:
            queue.append((id, 60*5))

        for (id, skip_timeout) in queue:
            logger.debug(f"hn fetch: {current_item} {id} {skip_timeout}")

            if redis.sismember(__redis_comment_set_key(platform), id):
                continue

            item = fetch_item(platform, id, client=client)
            if item:
                process_item(platform, item, redis=redis, skip_timeout=skip_timeout)
                time.sleep(0.1)

        cache.set(cache_current_item_key, current_item, timeout=None)


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_fetch_hn(self):
    _worker_fetch('h')


@shared_task(bind=True, ignore_result=True)
@celery_util.singleton(timeout=None, blocking_timeout=0.1)
def worker_fetch_laarc(self):
    _worker_fetch('a')


def submit_story(title, url, submit_from_dev=False):
    user = os.getenv('HN_USERNAME')
    password = os.getenv('HN_PASSWORD')

    logger.info(f"HN: submit {user} {title} {url}")

    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
        if not submit_from_dev:
            return True

    c = http.client()
    c.post(
        'https://news.ycombinator.com/login',
        data={
            'acct': user,
            'pw': password,
        },
    )

    time.sleep(1)

    submit_response = c.get('https://news.ycombinator.com/submit')

    h = http.parse_html(submit_response)

    csrf_token = h.select_one('input[name=fnid]')['value']

    time.sleep(2)
    print(url)
    post_response = c.post(
        'https://news.ycombinator.com/r',
        data={
            'title': title,
            'url': url,
            'fnop': 'submit-page',
            'fnid': csrf_token,
        },
    )

    if post_response.status_code != 200:
        logger.error(
            f'HN: submission failed {title} {url}: {post_response.status}')
        return False

    return True


def submit_comment(post_id, comment, submit_from_dev=False):
    user = os.getenv('HN_USERNAME')
    password = os.getenv('HN_PASSWORD')

    logger.info(f"HN: submit {user} {post_id} {comment}")

    if os.getenv('DJANGO_DEVELOPMENT', '').lower() == 'true':
        if not submit_from_dev:
            return True

    c = http.client()
    c.post(
        'https://news.ycombinator.com/login',
        data={
            'acct': user,
            'pw': password,
        },
    )

    time.sleep(1)

    comment_response = c.get(f'https://news.ycombinator.com/item?id={post_id}')

    h = http.parse_html(comment_response)

    hmac = h.select_one('input[name=hmac]')['value']

    time.sleep(2)

    post_response = c.post(
        'https://news.ycombinator.com/comment',
        data={
            'parent': post_id,
            'goto': f"item?id={post_id}",
            'hmac': hmac,
            'text': comment
        },
    )

    if post_response.status_code != 200:
        logger.error(
            f'HN: comment failed {post_id} {comment}: {post_response.status}')
        return False

    return True


@shared_task(ignore_result=True)
@celery_util.singleton()
def submit_discussions():
    _submit_discussions()


# todo: post only stories in the third quantile
#       https://stackoverflow.com/questions/59686945/django-postgres-percentile-median-and-group-by


def _submit_discussions():
    cache_prefix = 'hn:submitted:'
    three_days_ago = timezone.now() - datetime.timedelta(days=3)
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)

    subreddits = [
        'programming', 'python', 'ada', 'angular', 'angular2', 'angularjs',
        'archlinux', 'asm', 'awk', 'bsd', 'c_programming', 'ceylon', 'clojure',
        'cobol', 'compsci', 'coq', 'cpp', 'csharp', 'css', 'd_language',
        'dartlang', 'database', 'datalog', 'delphi', 'devops', 'django',
        'docker', 'dylanlang', 'economy', 'elixir', 'elm', 'erlang', 'forth',
        'fsharp', 'gamedev', 'geopolitics', 'golang', 'haskell', 'idris',
        'iolanguage', 'java', 'javascript', 'julia', 'kotlin', 'laravel',
        'rust', 'scheme', 'technology'
    ]

    stories = models.Discussion.objects.\
        filter(created_at__gte=three_days_ago).\
        filter(score__gte=5).\
        filter(comment_count__gte=5)

    stories = stories.filter(
        Q(platform='u') | Q(platform='l')
        | (Q(platform='r') & Q(tags__overlap=subreddits)))

    logger.info(f"hn submit: potential stories: {stories.count()}")

    for story in stories:
        u = story.schemeless_story_url.lower()
        cu = discussions.canonical_url(u)
        if cache.get(cache_prefix + u) or cache.get(cache_prefix + cu):
            logger.info(f"hn submit: story in cache {story}")
            continue

        related_discussions, _, _ = models.Discussion.of_url(
            story.story_url, only_relevant_stories=False)

        total_comment_count = 0
        total_score = 0
        for rd in related_discussions:
            factor = 1
            if rd.platform == 'l':
                factor = 3
            total_comment_count += rd.comment_count * factor
            total_score += rd.score * factor

        if story.platform != 'u':
            if not (total_comment_count > 20 or total_score > 100):
                logger.info(
                    f"hn submit: story not relevant {story} {total_comment_count} {total_score}"
                )
                continue

        already_submitted = False

        # see if this story was recently submitted
        for rd in related_discussions:
            if rd.platform == 'h' and rd.created_at >= seven_days_ago:
                already_submitted = True

        if already_submitted:
            logger.info(f"hn submit: already submitted {story}")
            continue

        logger.info(f"hn submit: submit {story}")

        ok = submit_story(story.title, story.story_url)
        if ok:
            cache.set(cache_prefix + u, 1, timeout=60 * 60 * 24 * 14)

        break


def previous_discussions_comment(story, previous_discussions):
    comment = "Other threads:"

    c = 0
    for pd in previous_discussions:
        if pd.comment_count > 30 or os.getenv('DJANGO_DEVELOPMENT',
                                              '').lower() == "true":
            comment += f"""

{pd.discussion_url()} [{pd.created_at.date().isoformat()}] ({pd.comment_count} comments)"""
            c += 1

    if c == 0:
        return None

    comment += f"""

All discussions: {util.discussions_url(story.story_url)}"""
    comment += f"""

Discussions with similar title: {util.discussions_url(story.title)}"""

    comment += f"""

Archive: {archiveis.archive_url(story.story_url)}"""

    return comment


@shared_task(ignore_result=True)
@celery_util.singleton()
def submit_previous_discussions():
    _submit_previous_discussions()


def _submit_previous_discussions():
    cache_prefix = 'hn:submitted_previous_discussions:'
    three_days_ago = timezone.now() - datetime.timedelta(days=3)

    hn_stories = models.Discussion.objects.\
        filter(created_at__gte=three_days_ago).\
        filter(score__gte=10).\
        filter(comment_count__gte=1).\
        filter(platform='h').\
        order_by('-created_at')

    logger.info(f"hn prev submit: potential stories: {hn_stories.count()}")

    for story in hn_stories:
        key = cache_prefix + story.id
        if cache.get(key):
            logger.info(f"hn prev submit: story in cache {story}")
            continue

        related_discussions, _, _ = models.Discussion.of_url(
            story.story_url, only_relevant_stories=False)

        related_discussions = related_discussions.exclude(
            platform_id=story.platform_id)

        related_discussions.order_by('-created_at', '-comment_count')

        total_comment_count = 0
        total_score = 0
        for rd in related_discussions:
            factor = 1
            if rd.platform == 'l':
                factor = 3
            if rd.platform == 'u':
                factor = 4
            if rd.platform == 'r':
                factor = 0.5
            total_comment_count += rd.comment_count * factor
            if rd.platform != 'u':
                total_score += rd.score * factor

        if not (total_comment_count > 150):
            logger.info(
                f"hn prev submit: story not relevant {story} {total_comment_count} {total_score}"
            )
            if not os.getenv('DJANGO_DEVELOPMENT', ''):
                continue

        if not len(related_discussions) > 2:
            logger.info(
                f"hn prev submit: story not relevant {len(related_discussions)}"
            )
            if not os.getenv('DJANGO_DEVELOPMENT', ''):
                continue

        comment = previous_discussions_comment(story, related_discussions)
        if not comment:
            logger.info(
                f"hn prev submit: not enough interesting discussions {story}")
            continue

        logger.info(f"hn prev submit: submit {story}")

        archiveis.capture.delay(story.story_url)

        ok = submit_comment(story.id, comment)
        if ok:
            cache.set(key, 1, timeout=60 * 60 * 24 * 14)

        break
