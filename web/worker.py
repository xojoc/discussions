import logging
import celery
from django.core.cache import cache
import gevent
from gevent.hub import get_hub

logger = logging.getLogger(__name__)

cache_graceful_exit_key = 'discussions:worker:graceful_exit'


@celery.signals.worker_ready.connect
def celery_worker_ready(signal, sender, **kwargs):
    # wait for entry to expire
    return
    # cache.delete(cache_graceful_exit_key)


def __patch_greenlet(f):
    def inner(*args, **kwargs):
        return gevent.spawn(f, *args, **kwargs)
    return inner


@__patch_greenlet
def __cache_set():
    cache.set(cache_graceful_exit_key, 1, timeout=60*3)


def __timer(after, repeat, f):
    t = get_hub().loop.timer(after, repeat)
    t.start(f)
    return t


@celery.signals.worker_shutting_down.connect
def celery_worker_shutting_down(**kwargs):
    __timer(1, 0, __cache_set)


def graceful_exit(task):
    return cache.get(cache_graceful_exit_key)
