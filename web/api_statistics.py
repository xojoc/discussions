# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
from django_redis import get_redis_connection

cache_prefix = "api"


def __get_statistics_key(api_version, token):
    return f"discussions:{cache_prefix}:statistics:{api_version}:{token}"


def track(request):
    r = get_redis_connection("default")

    view_name = request.resolver_match.view_name
    api_version = view_name.split(":")[0]
    endpoint = view_name.split(":")[1]
    hash_key = __get_statistics_key(api_version, request.auth.token)

    field = f"{endpoint}"

    r.hincrby(hash_key, field, 1)


def get(api_version, token, endpoint=None, redis=None):
    r = redis if redis else get_redis_connection("default")

    hash_key = __get_statistics_key(api_version, token)

    if endpoint:
        return int(r.hget(hash_key, endpoint) or 0)

    stats = r.hgetall(hash_key) or {}
    return {key.decode("utf-8"): int(val) for key, val in stats.items()}
