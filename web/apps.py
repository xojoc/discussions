from django.apps import AppConfig
import logging
from web import twitter
import os
from django.db.backends.signals import connection_created

logger = logging.getLogger(__name__)


class WebConfig(AppConfig):
    name = 'web'

    def __twitter_configuration(self):
        twitter.configuration['api_key'] = os.getenv('TWITTER_ACCESS_API_KEY')
        twitter.configuration['api_secret_key'] = os.getenv(
            'TWITTER_ACCESS_API_SECRET_KEY')
        for bot_name, bot_values in twitter.configuration['bots'].items():
            n = bot_name.upper()
            token = os.getenv(f"TWITTER_{n}_TOKEN")
            token_secret = os.getenv(f"TWITTER_{n}_TOKEN_SECRET")
            if token and token_secret:
                bot_values['token'] = token
                bot_values['token_secret'] = token_secret

    def __connection_created_signal_handler(sender, connection, **kwargs):
        if sender.vendor == 'postgresql':
            connection.cursor().execute("""
            set pg_trgm.similarity_threshold = 0.6;
            set pg_trgm.word_similarity_threshold = 0.68;
            """)

    def __set_trigram_threshold(self):
        connection_created.connect(
            WebConfig.__connection_created_signal_handler)

    def ready(self):
        from web import reddit

        with open("web/reddit_subreddit_blacklist") as f:
            reddit.subreddit_blacklist = {
                x.lower().strip()
                for x in f.read().splitlines()
            }

        with open("web/reddit_subreddit_whitelist") as f:
            reddit.subreddit_whitelist = {
                x.lower().strip()
                for x in f.read().splitlines()
            }

        self.__twitter_configuration()
        self.__set_trigram_threshold()
