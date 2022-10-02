import re
from django.urls import reverse

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed
from web import weekly, models


def filter_control_chars(method):
    def wrapped(self, obj):
        result = method(self, obj)
        return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", result)

    return wrapped


class XmlMimeTypeRss2Feed(Rss201rev2Feed):
    content_type = "application/xml; charset=utf-8"


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
