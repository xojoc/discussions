import logging
import os
import random
import urllib

from django.apps import AppConfig
from django.conf import settings
from django.db.backends.signals import connection_created

logger = logging.getLogger(__name__)


class WebConfig(AppConfig):
    name = "web"

    def __topics(self):
        from web import topics

        for topic_key, topic in topics.topics.items():
            topic[
                "email"
            ] = f"{settings.EMAIL_TO_PREFIX}weekly_{topic_key}@discu.eu"
            topic[
                "mailto_subscribe"
            ] = f"mailto:{topic['email']}?" + urllib.parse.urlencode(
                [
                    ("subject", f"Subscribe to {topic['name']}"),
                    ("body", "subscribe (must be first word)"),
                ]
            )
            topic[
                "mailto_unsubscribe"
            ] = f"mailto:{topic['email']}?" + urllib.parse.urlencode(
                [
                    ("subject", f"Unsubscribe from {topic['name']}"),
                    ("body", "unsubscribe (must be first word)"),
                ]
            )

        for topic_key, topic in topics.topics.items():
            topic["topic_key"] = topic_key
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
                    mastodon["access_token"] = mastodon_access_token

    def __reddit_configuration(self):
        from web import reddit

        with open("web/reddit_subreddit_blacklist") as f:
            reddit.subreddit_blacklist = {
                x.lower().strip() for x in f.read().splitlines()
            }

        with open("web/reddit_subreddit_whitelist") as f:
            reddit.subreddit_whitelist = {
                x.lower().strip() for x in f.read().splitlines()
            }

    def __connection_created_signal_handler(sender, connection, **kwargs):
        return
        # if sender.vendor == 'postgresql':
        #     connection.cursor().execute("""
        #     set pg_trgm.similarity_threshold = 0.63;
        #     set pg_trgm.word_similarity_threshold = 0.90;
        #     set pg_trgm.strict_word_similarity_threshold = 0.60;
        #     """)

        # set statement_timeout = 600000;

    def __set_database_parameters(self):
        connection_created.connect(
            WebConfig.__connection_created_signal_handler
        )

    def __nltk_download_data(self):
        return
        # import nltk
        # nltk.download('punkt')
        # nltk.download('stopwords')

    def ready(self):
        random.seed()
        self.__topics()
        self.__reddit_configuration()
        self.__set_database_parameters()
        self.__nltk_download_data()
