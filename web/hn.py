from web import util, archiveis
import os
import logging
from django.utils.timezone import make_aware
import datetime
from django_redis import get_redis_connection
from web import http, models, discussions
from celery import shared_task
from discussions.settings import APP_CELERY_TASK_MAX_TIME
import time
from web import celery_util
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache

logger = logging.getLogger(__name__)

r_skip_prefix = "discussions:hn:skip:"
r_revisit_set = "discussions:hn:revisit_set"
r_revisit_max_id = "discussions:hn:revisit_max_id"


@shared_task(ignore_result=True)
def process_item(item, revisit_max_id=None, redis=None, skip_timeout=60 * 60):
    if not item:
        return

    if not redis:
        redis = get_redis_connection("default")

    platform_id = f"h{item.get('id')}"

    if revisit_max_id is None or item.get('id') > revisit_max_id - 10_000:
        for kid in item.get('kids', []):
            redis.setex(r_skip_prefix + str(kid), skip_timeout, 1)

    if item.get('deleted'):
        models.Discussion.objects.filter(pk=platform_id).delete()
        return

    if item.get('type') != 'story':
        return

    if not item.get('url'):
        return

    if item.get('dead'):
        models.Discussion.objects.filter(pk=platform_id).delete()
        return

    redis.sadd(r_revisit_set, item.get('id'))

    if not item.get('time'):
        logger.info(f"HN no time: {item}")
        return

    # if not item.get('descendants'):
    #    return

    # if item.get('score') < 0:
    #    return

    created_at = datetime.datetime.fromtimestamp(item.get('time'))

    scheme, url = discussions.split_scheme(item.get('url'))
    if len(url) > 2000:
        return
    if not scheme:
        return

    canonical_url = discussions.canonical_url(url)

    try:
        discussion = models.Discussion.objects.get(pk=platform_id)
        discussion.comment_count = item.get('descendants') or 0
        discussion.score = item.get('score') or 0
        discussion.created_at = make_aware(created_at)
        discussion.scheme_of_story_url = scheme
        discussion.schemeless_story_url = url
        discussion.canonical_story_url = canonical_url
        discussion.title = item.get('title')
        discussion.save()
    except models.Discussion.DoesNotExist:
        models.Discussion(platform_id=platform_id,
                          comment_count=item.get('descendants') or 0,
                          score=item.get('score') or 0,
                          created_at=make_aware(created_at),
                          scheme_of_story_url=scheme,
                          schemeless_story_url=url,
                          canonical_story_url=canonical_url,
                          title=item.get('title')).save()


def fetch_item(id, revisit_max_id=None, c=None, redis=None):
    if not c:
        c = http.client(with_cache=False)
    if not redis:
        redis = get_redis_connection("default")

    if revisit_max_id:
        if (id < revisit_max_id and (not redis.sismember(r_revisit_set, id))):
            return

    if redis.exists(r_skip_prefix + str(id)):
        return

    # xojoc: if this fails, we let the whole task fail so it gets relaunched
    #        with the same parameters
    try:
        item = c.get(f"https://hacker-news.firebaseio.com/v0/item/{id}.json",
                     timeout=11.05).json()
    except Exception as e:
        time.sleep(7)
        raise (e)
    return item


@shared_task(ignore_result=True)
def fetch_process_item(id):
    item = fetch_item(id)
    process_item(item)


def fetch_discussions(from_id, max_id):
    c = http.client(with_cache=False)
    redis = get_redis_connection("default")
    revisit_max_id = int(redis.get(r_revisit_max_id) or -1)

    start_time = time.monotonic()
    id = from_id

    while time.monotonic() - start_time <= APP_CELERY_TASK_MAX_TIME:
        item = fetch_item(id, revisit_max_id=revisit_max_id, c=c, redis=redis)
        process_item.delay(item, revisit_max_id=revisit_max_id)
        id += 1
        if id > max_id:
            break

    redis.set(r_revisit_max_id, id)
    return id


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_all_hn_discussions():
    r = get_redis_connection("default")
    redis_prefix = 'discussions:fetch_all_hn_discussions:'
    current_index = int(r.get(redis_prefix + 'current_index') or 0)
    max_index = int(r.get(redis_prefix + 'max_index') or 0)
    if not current_index or not max_index or (current_index > max_index):
        max_index = int(
            http.client(with_cache=False).get(
                "https://hacker-news.firebaseio.com/v0/maxitem.json").content
        ) + 1
        r.set(redis_prefix + 'max_index', max_index)
        current_index = 1

    current_index = fetch_discussions(current_index, max_index)

    r.set(redis_prefix + 'current_index', current_index)


@shared_task(ignore_result=True)
def fetch_update(id, redis=None, skip_timeout=60 * 5):
    if redis is None:
        redis = get_redis_connection("default")
    item = fetch_item(id, redis=redis)
    if not item:
        return
    redis.setex(r_skip_prefix + str(id), skip_timeout, 1)
    if item.get("type") == "story":
        process_item.delay(item, skip_timeout=skip_timeout)
    if item.get("type") == "comment":
        if item.get("parent"):
            fetch_update(item.get("parent"),
                         redis=redis,
                         skip_timeout=skip_timeout)


@shared_task(ignore_result=True)
@celery_util.singleton(blocking_timeout=3)
def fetch_updates():
    c = http.client(with_cache=False)
    updates = c.get("https://hacker-news.firebaseio.com/v0/updates.json",
                    timeout=7.05).json()

    for id in updates.get('items'):
        fetch_update.delay(id)


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

All discussions: {util.discussions_url(story.schemeless_story_url)}"""
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
