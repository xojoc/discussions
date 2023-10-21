# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import os

from django.core.cache import cache

from web import http


def get_followers_count(usernames):
    cache_timeout = 24 * 60 * 60
    followers_count = {}

    access_token = os.getenv("MASTODON_DISCUSSIONS_ACCESS_TOKEN")

    client = http.client(with_cache=False)

    api_url = "https://mastodon.social/api/v2/search"
    auth = {"Authorization": f"Bearer {access_token}"}
    parameters = {"limit": 5, "resolve": True, "type": "accounts"}

    for username in usernames:
        key = f"mastodon:followers:{username}"
        fc = cache.get(key)
        if fc:
            followers_count[username] = fc
        else:
            parameters["q"] = username
            res = client.get(api_url, params=parameters, headers=auth)

            if not res.ok:
                continue

            for user in res.json()["accounts"]:
                if user["username"].lower() != username:
                    continue

                followers_count[username] = user["followers_count"]
                cache.set(key, user["followers_count"], cache_timeout)

    return followers_count
