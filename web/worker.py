# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging

import celery
import celery.signals

# import gevent
from django.core.cache import cache
from django_redis import get_redis_connection

# from gevent.hub import get_hub
from web import celery_util

logger = logging.getLogger(__name__)

cache_graceful_exit_key = "discussions:worker:graceful_exit"


def __patch_greenlet(f):
    _ = f

    # def inner(*args, **kwargs):
    #     return gevent.spawn(f, *args, **kwargs)
    #
    # return inner


@__patch_greenlet
def __cache_set():
    cache.set(cache_graceful_exit_key, 1, timeout=60 * 4)


def __timer(after, repeat, f):
    _ = after
    _ = repeat
    _ = f
    # t = get_hub().loop.timer(after, repeat)
    # t.start(f)
    # return t


@celery.signals.worker_shutting_down.connect
def celery_worker_shutting_down(**kwargs):
    _ = kwargs
    __timer(1, 0, __cache_set)


def graceful_exit(task: celery.Task) -> bool:
    e = cache.get(cache_graceful_exit_key)
    if e:
        return True

    k = celery_util.lock_key(task)
    redis = get_redis_connection()
    redis.expire(k, 60 * 10)
    return False
