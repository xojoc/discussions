from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class WebConfig(AppConfig):
    name = 'web'

    def ready(self):
        from web import reddit

        with open("web/reddit_subreddit_blacklist") as f:
            reddit.subreddit_blacklist = {x.lower().strip() for x in f.read().splitlines()}

        with open("web/reddit_subreddit_whitelist") as f:
            reddit.subreddit_whitelist = {x.lower().strip() for x in f.read().splitlines()}