import re

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.template import loader as template_loader
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed

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

    @filter_control_chars
    def title(self, obj):
        return f"{obj['topic']['name']} weekly - discu.eu"

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

    @filter_control_chars
    def description(self, obj):
        return f"Weekly recap for {obj['topic']['name']} with articles, projects and tutorials."

    def author_name(self, obj):
        return "discu.eu"

    def author_email(self, obj):
        return "feed@discu.eu"

    def author_link(self, obj):
        return "https://discu.eu"

    def categories(self, obj):
        return tags.normalize(obj["topic"]["tags"])

    def feed_copyright(self, obj):
        pass

    def ttl(self, obj):
        return 60 * 60

    def get_object(self, request, topic, rss_id, **kwargs):
        user = models.CustomUser.objects.get(rss_id=rss_id)
        return {
            "topic_key": topic,
            "topic": topics.topics[topic],
            "user": user,
        }

    def items(self, obj):
        weeks = weekly.last_nth_yearweeks(obj["topic_key"], 10)
        if not obj["user"].is_premium:
            weeks = weeks[-2:]
        return [(obj,) + e for e in weeks]

    @filter_control_chars
    def item_title(self, item):
        obj, year, week = item
        return f"{obj['topic']['name']} recap for week {week}/{year}"

    @filter_control_chars
    def item_description(self, item):
        obj, year, week = item
        ctx = weekly.topic_week_context_cached(obj["topic_key"], year, week)
        content = template_loader.render_to_string(
            "web/weekly_topic_week_feed.html", {"ctx": ctx}
        )
        return content

    def item_link(self, item):
        obj, year, week = item
        return (
            settings.APP_SCHEME
            + "://"
            + settings.APP_DOMAIN
            + reverse(
                "web:weekly_topic_week", args=[obj["topic_key"], year, week]
            )
        )

    def item_pubdate(self, item):
        obj, year, week = item
        return weekly.week_end(year, week)


class AtomWeeklyFeed(WeeklyFeed):
    feed_type = Atom1Feed
    subtitle = WeeklyFeed.description


class WeeklyFeedSingle(Feed):
    feed_type = XmlMimeTypeRss2Feed

    @filter_control_chars
    def title(self, obj):
        return f"{obj} - discu.eu"

    def link(self, obj):
        return reverse(
            "web:weekly_single_rss_feed",
            args=[obj["topic"], obj["user"].rss_id],
        )

    @filter_control_chars
    def description(self, obj):
        return f"{obj} - discu.eu"

    def author_name(self, obj):
        return "discu.eu"

    def author_email(self, obj):
        return "contact@keepmeon.top"

    def author_link(self, obj):
        return "https://discu.eu"

    def categories(self, obj):
        pass

    def feed_copyright(self, obj):
        pass

    def ttl(self, obj):
        return 5

    def items(self, obj):
        return weekly.base_query(obj["topic"]).order_by("created_at")[:10]

    def get_object(self, request, topic, rss_id, **kwargs):
        user = models.CustomUser.objects.get(rss_id=rss_id)
        return {"topic": topic, "user": user}

    @filter_control_chars
    def item_title(self, item):
        return item.title

    @filter_control_chars
    def item_description(self, item):
        return f"Discussions: {item.discussion_url}"

    def item_link(self, item):
        return item.story_url
        # return reverse("web:story_short_url", args=[item.platform_id])

    # def item_author_name(self, item):
    #     return item.author

    # def item_author_email(self, item):
    #     return item.author_email

    # def item_author_link(self, item):
    #     return item.author_url

    # def item_pubdate(self, item):
    #     return item.publication_date

    # def item_updateddate(self, item):
    #     return item.update_date

    def item_categories(self, item):
        pass
        # fixme

    def item_copyright(self, obj):
        pass
        # fixme


class AtomWeeklyFeedSingle(WeeklyFeedSingle):
    feed_type = Atom1Feed
    subtitle = WeeklyFeedSingle.description
