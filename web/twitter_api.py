# Copyright 2023 Alexandru Cojocaru AGPLv3 or later - no warranty!
"""Wrappers around Twitter API."""

import logging
import os
import typing

import tweepy
from django.core.cache import cache

from web import topics

logger = logging.getLogger(__name__)

current_plan = "free"


def get_followers_count(usernames: list[str]) -> dict[str, int]:
    """Get Twitter followers for usernames.

    Args:
        usernames: twitter profiles for which to get the follower count

    Returns:
        follower count for each user
    """
    # TODO: reduce to 24 when upgrading twitter plan,
    #       and use a single user to get counts
    cache_timeout = 48 * 60 * 60
    followers_count = {}

    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")

    for username in usernames:
        account = topics.get_account_configuration("twitter", username)
        if not account:
            logger.warning(
                "Twitter bot: %s non properly configured",
                username,
            )
            return {}

        token = account["token"]
        token_secret = account["token_secret"]

        if (
            not consumer_key
            or not consumer_secret
            or not token
            or not token_secret
        ):
            logger.warning(
                "Twitter bot: %s non properly configured",
                username,
            )
            return {}

        client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=token,
            access_token_secret=token_secret,
            wait_on_rate_limit=False,
        )
        key = f"twitter:followers:{username}"
        fc = cache.get(key)
        if fc:
            followers_count[username] = fc
        else:
            try:
                user = client.get_me(user_fields=["public_metrics"])
                user = typing.cast(tweepy.Response, user)
                fc = user.data["public_metrics"]["followers_count"]
                followers_count[username] = fc
                cache.set(key, fc, cache_timeout)
            except tweepy.TweepyException:
                logger.warning("twitter followers count", exc_info=True)

    return followers_count
