# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import re

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.template import loader as template_loader
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed
from typing_extensions import override

from web import models, tags, topics, weekly


def filter_control_chars(method):
    def wrapped(self, obj):
        result = method(self, obj)
        return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", result)

    return wrapped


class XmlMimeTypeRss2Feed(Rss201rev2Feed):
    content_type = "application/xml; charset=utf-8"


class WeeklyFeed(Feed):
    feed_type = XmlMimeTypeRss2Feed

    @override
    @filter_control_chars
    def title(self, obj):
        return f"{obj['topic']['name']} weekly - discu.eu"

    @override
    def link(self, obj):
        return (
            settings.APP_SCHEME
            + "://"
            + settings.APP_DOMAIN
            + reverse(
                "web:weekly_topic",
                args=[obj["topic_key"]],
            )
        )

    @override
    @filter_control_chars
    def description(self, obj):
        return f"Weekly recap for {obj['topic']['name']} with articles, projects and tutorials."

    @override
    def author_name(self, obj):
        return "discu.eu"

    @override
    def author_email(self, obj):
        return "feed@discu.eu"

    @override
    def author_link(self, obj):
        return "https://discu.eu"

    @override
    def categories(self, obj):
        return tags.normalize(obj["topic"]["tags"])

    @override
    def feed_copyright(self, obj):
        pass

    @override
    def ttl(self, obj):
        return 60 * 60

    @override
    def get_object(self, request, topic, rss_id, **kwargs):
        user = models.CustomUser.objects.get(rss_id=rss_id)
        return {
            "topic_key": topic,
            "topic": topics.topics[topic],
            "user": user,
        }

    @override
    def items(self, obj):
        weeks = weekly.last_nth_yearweeks(obj["topic_key"], 10)
        if not obj["user"].is_premium:
            weeks = weeks[-2:]
        return [(obj, *e) for e in weeks]

    @override
    @filter_control_chars
    def item_title(self, item):
        obj, year, week = item
        return f"{obj['topic']['name']} recap for week {week}/{year}"

    @override
    @filter_control_chars
    def item_description(self, item):
        obj, year, week = item
        ctx = weekly.topic_week_context_cached(obj["topic_key"], year, week)
        return template_loader.render_to_string(
            "web/weekly_topic_week_feed.html",
            {"ctx": ctx},
        )

    @override
    def item_link(self, item):
        obj, year, week = item
        return (
            settings.APP_SCHEME
            + "://"
            + settings.APP_DOMAIN
            + reverse(
                "web:weekly_topic_week",
                args=[obj["topic_key"], year, week],
            )
        )

    @override
    def item_pubdate(self, item):
        _, year, week = item
        return weekly.week_end(year, week)


class AtomWeeklyFeed(WeeklyFeed):
    feed_type = Atom1Feed
    subtitle = WeeklyFeed.description


class WeeklyFeedSingle(Feed):
    feed_type = XmlMimeTypeRss2Feed

    @override
    @filter_control_chars
    def title(self, obj):
        return f"{obj} - discu.eu"

    @override
    def link(self, obj):
        return reverse(
            "web:weekly_single_rss_feed",
            args=[obj["topic"], obj["user"].rss_id],
        )

    @override
    @filter_control_chars
    def description(self, obj):
        return f"{obj} - discu.eu"

    @override
    def author_name(self, obj):
        return "discu.eu"

    @override
    def author_email(self, obj):
        return "hi@discu.eu"

    @override
    def author_link(self, obj):
        return "https://discu.eu"

    @override
    def categories(self, obj):
        pass

    @override
    def feed_copyright(self, obj):
        pass

    @override
    def ttl(self, obj):
        return 5

    @override
    def items(self, obj):
        return weekly.base_query(obj["topic"]).order_by("created_at")[:10]

    @override
    def get_object(self, request, topic, rss_id, **kwargs):
        user = models.CustomUser.objects.get(rss_id=rss_id)
        return {"topic": topic, "user": user}

    @override
    @filter_control_chars
    def item_title(self, item):
        return item.title

    @override
    @filter_control_chars
    def item_description(self, item):
        return f"Discussions: {item.discussion_url}"

    @override
    def item_link(self, item):
        return item.story_url

    # def item_author_name(self, item):

    # def item_author_email(self, item):

    # def item_author_link(self, item):

    # def item_pubdate(self, item):

    # def item_updateddate(self, item):

    @override
    def item_categories(self, item):
        pass
        # TODO: add categories

    @override
    def item_copyright(self, obj):
        pass
        # TODO: add copyright


class AtomWeeklyFeedSingle(WeeklyFeedSingle):
    feed_type = Atom1Feed
    subtitle = WeeklyFeedSingle.description
