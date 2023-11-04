# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
import os
import random
import urllib
import urllib.parse
from email.utils import formataddr
from pathlib import Path

from django.apps import AppConfig
from django.conf import settings
from django.db.backends.signals import connection_created
from typing_extensions import override

logger = logging.getLogger(__name__)


def connection_created_signal_handler(sender, connection, **kwargs):
    _ = (sender, connection, kwargs)
    # if sender.vendor == 'postgresql':
    #     connection.cursor().execute("""
    #     set pg_trgm.similarity_threshold = 0.63;
    #     set pg_trgm.word_similarity_threshold = 0.90;
    #     set pg_trgm.strict_word_similarity_threshold = 0.60;
    #     """)

    # set statement_timeout = 600000;


class WebConfig(AppConfig):
    name = "web"

    @classmethod
    def __topics(cls):
        from web import topics  # noqa: PLC0415

        for topic_key, topic in topics.topics.items():
            topic[
                "email"
            ] = f"{settings.EMAIL_TO_PREFIX}weekly_{topic_key}@discu.eu"
            topic["from_email"] = formataddr(
                (
                    f"{topic['name']} Weekly",
                    topic["email"],
                ),
            )
            topic["mailto_subscribe"] = (
                f"mailto:{topic['email']}?"
                + urllib.parse.urlencode(
                    [
                        ("subject", f"Subscribe to {topic['name']}"),
                        ("body", "subscribe (must be first word)"),
                    ],
                )
            )
            topic["mailto_unsubscribe"] = (
                f"mailto:{topic['email']}?"
                + urllib.parse.urlencode(
                    [
                        ("subject", f"Unsubscribe from {topic['name']}"),
                        ("body", "unsubscribe (must be first word)"),
                    ],
                )
            )

        for topic in topics.topics.values():
            twitter = topic.get("twitter")
            if not twitter:
                continue
            twitter_account = twitter.get("account")
            if not twitter_account:
                continue

            n = twitter_account.upper()

            token = os.getenv(f"TWITTER_{n}_TOKEN")
            token_secret = os.getenv(f"TWITTER_{n}_TOKEN_SECRET")
            if token and token_secret:
                twitter["token"] = token
                twitter["token_secret"] = token_secret

            mastodon = topic.get("mastodon")
            if mastodon:
                mastodon_access_token = os.getenv(f"MASTODON_{n}_ACCESS_TOKEN")
                if mastodon_access_token:
                    mastodon["token"] = mastodon_access_token

    @classmethod
    def __reddit_configuration(cls):
        from web import reddit  # noqa: PLC0415

        with Path("web/reddit_subreddit_blacklist").open() as f:
            reddit.subreddit_blacklist = {
                x.lower().strip() for x in f.read().splitlines()
            }

        with Path("web/reddit_subreddit_whitelist").open() as f:
            reddit.subreddit_whitelist = {
                x.lower().strip() for x in f.read().splitlines()
            }

    @classmethod
    def __set_database_parameters(cls):
        connection_created.connect(
            connection_created_signal_handler,
        )

    @classmethod
    def __nltk_download_data(cls):
        return

    @classmethod
    def __set_up_signals(cls):
        from . import (  # noqa: PLC0415
            mention,
            stripe_util,
        )

        _ = mention
        _ = stripe_util

    @override
    def ready(self):
        random.seed()
        self.__topics()
        self.__reddit_configuration()
        self.__set_database_parameters()
        self.__nltk_download_data()
        self.__set_up_signals()
