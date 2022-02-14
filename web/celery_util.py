import functools
import logging
from django_redis import get_redis_connection
from redis.exceptions import LockError
from discussions.settings import APP_CELERY_TASK_MAX_TIME
import sentry_sdk

logger = logging.getLogger(__name__)


class EndOfIteration(Exception):
    pass


class RepeatCurrentIndex(Exception):
    pass


def split_task(
    redis_prefix,
    get_start_index,
    get_max,
    step,
    callback,
    infinite_repeat=True,
):
    r = get_redis_connection("default")
    current_index = int(r.get(redis_prefix + "current_index") or 0)
    max_index = int(r.get(redis_prefix + "max_index") or 0)
    if (
        not current_index
        or not max_index
        or (current_index > max_index and infinite_repeat)
    ):
        max_index = get_max()
        r.set(redis_prefix + "max_index", max_index)
        current_index = get_start_index(max_index)

    if current_index > max_index and not infinite_repeat:
        return True

    try:
        callback(current_index, min(current_index + step, max_index))
    except EndOfIteration:
        r.set(redis_prefix + "current_index", max_index + 1)
    except RepeatCurrentIndex:
        pass
    except Exception as e:
        logger.error(f"split_task: {callback.__name__}: {e}")
        raise
    else:
        r.set(redis_prefix + "current_index", current_index + step)


def lock_key(f):
    f_path = f"{f.__module__}.{f.__name__}".replace(".", ":")
    return "discussions:lock:" + f_path


def singleton(timeout=APP_CELERY_TASK_MAX_TIME * 5, blocking_timeout=0.1):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            r = get_redis_connection("default")
            lock_name = lock_key(f)

            logger.debug(f"Lock {lock_name}: {timeout}: {blocking_timeout}")

            try:
                with r.lock(
                    lock_name,
                    timeout=timeout,
                    blocking_timeout=blocking_timeout,
                ):

                    f(*args, **kwargs)
            except LockError:
                logger.debug(
                    f"Lock {lock_name} not acquired timeout = {timeout}, blocking_timeout = {blocking_timeout}"
                )
            except Exception as e:
                logger.warn(f"singleton {lock_name}: {e}")
                sentry_sdk.capture_exception(e)

        return wrapper

    return decorator
