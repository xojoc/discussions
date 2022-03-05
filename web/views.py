import itertools
import logging
from urllib.parse import quote
from urllib.parse import unquote as url_unquote

import urllib3
from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django_redis import get_redis_connection

from discussions import settings

from . import discussions, forms, mastodon, models, topics, util, weekly

logger = logging.getLogger(__name__)


def __log_query(q):
    if not q:
        return

    q = q.strip().lower()

    r = get_redis_connection()
    if q.startswith("http://") or q.startswith("https://"):
        r.zincrby("discussions:stats:query:url", 1, q)
    else:
        r.zincrby("discussions:stats:query:search", 1, q)


def discussions_context_cached(q):
    if util.is_dev():
        return discussions_context(q)

    if not q:
        return discussions_context(q)

    suffix = (q or "").lower().strip()

    key = "discussions_context:" + suffix
    touch_key = "touch:" + key
    ctx = cache.get(key)

    if ctx:
        if cache.get(touch_key):
            cache.touch(key, 30)
    else:
        ctx = discussions_context(q)
        if ctx and ctx["nothing_found"] is False:
            cache.set(key, ctx, 60)
            cache.set(touch_key, 1, timeout=60 * 3)

    return ctx


def discussions_context(q):
    ctx = {}

    q = (q or "").strip()

    url = (q or "").lower().strip()

    # ctx['statistics'] = models.Statistics.all_statistics()

    if url and not (url.startswith("http://") or url.startswith("https://")):
        ctx["absolute_url"] = "https://" + q
    else:
        ctx["absolute_url"] = q

    if q:
        ctx["link_canonical_url"] = util.discussions_canonical_url(q)

    ctx["original_query"] = q
    ctx["url"] = url
    if (
        (url.startswith("http://") or url.startswith("https://"))
        and " " not in url
        and len(url) >= 10
    ):
        ctx["is_url"] = True
    else:
        ctx["is_url"] = False
    ctx["display_discussions"] = False
    ctx["nothing_found"] = False
    ctx["title"] = ""
    if not ctx["url"]:
        return ctx
    ctx["display_discussions"] = True
    uds, cu, rcu = models.Discussion.of_url_or_title(ctx["url"])

    ctx["sql_query"] = ""
    if uds is not None:
        ctx["sql_query"] = str(uds.query)

    try:
        uds = list(uds)
    except Exception as e:
        logger.warn(e)
        uds = []

    # tds = tds[:11]
    tds = None

    ctx["canonical_url"] = cu

    # ds = sorted(ds, key=lambda x: x.platform_order)
    ctx["discussions"] = uds
    ctx["title_discussions"] = tds

    uds.sort(key=lambda i: i.platform)

    # We have to convert the iterator to a list, see: https://stackoverflow.com/a/16171518
    ctx["grouped_discussions"] = [
        (
            platform,
            models.Discussion.get_platform_name(platform),
            models.Discussion.get_platform_url(
                platform,
                preferred_external_url=discussions.PreferredExternalURL.Standard,
            ),
            models.Discussion.get_platform_tag_url(
                platform,
                preferred_external_url=discussions.PreferredExternalURL.Standard,
            ),
            list(uds),
        )
        for platform, uds in itertools.groupby(uds, lambda x: x.platform)
    ]

    # if q.startswith('http://') or\
    #    q.startswith('https://'):

    ctx["resource"] = models.Resource.by_url(cu)
    if ctx["resource"]:
        ctx["title"] = ctx["resource"].title
        ctx["inbound_resources"] = ctx["resource"].inbound_resources()
        if ctx["inbound_resources"] is not None:
            ctx["inbound_resources"] = ctx["inbound_resources"][:20]

    if not ctx.get("title"):
        if uds and (q.startswith("http://") or q.startswith("https://")):

            ctx["title"] = uds[0].title
        else:
            ctx["title"] = ctx["original_query"]

    if not uds and not ctx.get("inbound_resources"):
        ctx["display_discussions"] = False

    if not uds and not tds and not ctx.get("inbound_resources"):
        ctx["nothing_found"] = True

    return ctx


def get_submit_links(request, ctx):
    q = ctx["original_query"]
    url = None
    if q.lower().startswith("http://") or q.lower().startswith("https://"):
        url = quote(q)
    else:
        url = request.GET.get("submit_url")

    if not url:
        return

    ctx["submit_title"] = request.GET.get("submit_title") or ctx["title"] or ""
    t = quote(ctx.get("submit_title"))

    submit_links = {
        "Hacker News": f"https://news.ycombinator.com/submitlink?u={url}&t={t}",
        "Reddit": f"https://www.reddit.com/submit?url={url}&title={t}",
        "Lobsters": f"https://lobste.rs/stories/new?url={url}&title={t}",
        "Laarc": f"https://www.laarc.io/submitlink?u={url}&t={t}",
        "Barnacles": f"https://barnacl.es/stories/new?url={url}&title={t}",
        "Gambero": f"https://gambe.ro/stories/new?url={url}&title={t}",
    }

    ctx["submit_links"] = submit_links

    ctx["submit_links_visible"] = False
    if ctx["nothing_found"]:
        ctx["submit_links_visible"] = True


def index(request, path_q=None):
    host = request.get_host().partition(":")[0]
    if not request.path.startswith("/.well-known/"):
        if (
            host != "localhost"
            and host != "127.0.0.1"
            and host != "testserver"
            and host != settings.APP_DOMAIN
        ):
            r = "https://" + settings.APP_DOMAIN + request.get_full_path()
            return HttpResponsePermanentRedirect(r)

    if path_q:
        q = url_unquote(request.get_full_path()[len("/q/") :])
    else:
        q = request.GET.get("url")
        if not q:
            q = request.GET.get("q")

    q = q or ""

    ctx = discussions_context_cached(q)

    get_submit_links(request, ctx)

    if ctx.get("is_url"):
        url = ctx.get("url", "")
        u = urllib3.util.parse_url(url)
        if u.host:
            ctx["try_with_site_prefix"] = "site:" + u.host

    if ctx.get("submit_title") and not (
        ctx.get("submit_title").startswith("http://")
        or ctx.get("submit_title").startswith("https://")
    ):
        ctx["try_with_title"] = ctx.get("submit_title")

    if request.GET.get("submit_url") and (
        request.GET.get("submit_url").lower().startswith("http://")
        or request.GET.get("submit_url").lower().startswith("https://")
        or request.GET.get("submit_url").lower().startswith("ftp://")
    ):
        ctx["try_with_url"] = request.GET.get("submit_url")

    ctx["form"] = forms.QueryForm(request.GET)
    ctx["form"].fields["tags"].choices = [
        ("tag", "asdf"),
        ("tag2", "fdsa"),
        ("tag2", "fdsa"),
        ("tag2", "fdsa"),
    ]

    try:
        __log_query(q)
    except Exception as e:
        logger.warn(e)

    response = render(request, "web/discussions.html", {"ctx": ctx})

    if ctx["nothing_found"]:
        response.status_code = 404

    return response


def weekly_confirm_email(request):
    topic = request.GET.get("topic")
    subscriber_email = request.GET.get("email")
    try:
        subscriber = models.Subscriber.objects.get(
            topic=topic, email=subscriber_email
        )
    except models.Subscriber.DoesNotExist:
        subscriber = None

    if subscriber and subscriber.confirmed and not subscriber.unsubscribed:
        messages.warning(
            request,
            f"Email {subscriber_email} was already confirmed. If it wasn't you please write to hi@discu.eu",
        )
    elif subscriber and subscriber.verification_code == request.GET.get(
        "verification_code"
    ):
        subscriber.subscribe()
        subscriber.save()

        messages.success(
            request, f"Email {subscriber_email} confirmed. Thank you!"
        )
    else:
        messages.error(
            request,
            f"Something went wrong while trying to confirm email {subscriber_email}. Write to hi@discu.eu for assistance.",
        )

    redirect_to = "/"
    if topic:
        redirect_to = reverse("web:weekly_topic", args=[topic])
    else:
        redirect_to = reverse("web:weekly_index")

    return redirect(redirect_to, permanent=False)


def weekly_confirm_unsubscription(request):
    if request.method == "GET":
        form = forms.UnsubscribeForm(request.GET)
        topic_key = request.GET.get("topic")
        ctx = {
            "weekly_unsubscribe_form": form,
            "topic": topics.topics.get(topic_key),
        }
        return render(
            request, "web/weekly_unsubscribe_page.html", {"ctx": ctx}
        )
    elif request.method == "POST":
        topic = request.POST.get("topic")
        subscriber_email = request.POST.get("email")
        verification_code = request.POST.get("verification_code")

        try:
            subscriber = models.Subscriber.objects.get(
                topic=topic, email=subscriber_email
            )
        except models.Subscriber.DoesNotExist:
            subscriber = None

        if subscriber and subscriber.verification_code != verification_code:
            messages.error(
                request,
                "Something went wrong. Verification code doesn't match. Write to hi@discu.eu for assistance",
            )
        elif (
            subscriber and subscriber.confirmed and not subscriber.unsubscribed
        ):
            subscriber.unsubscribe()
            subscriber.save()
            messages.success(request, "You're now unsubscribed. Thank you!")
        else:
            messages.warning(
                request,
                "You were already unsubscribed. Write to hi@discu.eu for assistance.",
            )

        redirect_to = "/"
        if topic:
            redirect_to = reverse("web:weekly_topic", args=[topic])
        else:
            redirect_to = reverse("web:weekly_index")

        return redirect(redirect_to, permanent=False)


def __weekly_topic_subscribe_form(request, topic, ctx):
    form = forms.SubscriberForm(request.POST or None, initial={"topic": topic})

    if form.is_valid():
        subscriber = form.save()
        subscriber.send_confirmation_email()

        messages.success(
            request,
            f"Thank you! A confirmation email was sent to {subscriber.email}.",
        )

    ctx["weekly_subscribe_form"] = form
    return None


def weekly_index(request):
    ctx = weekly.index_context()
    response = __weekly_topic_subscribe_form(request, None, ctx)
    if response:
        return response
    response = render(request, "web/weekly_index.html", {"ctx": ctx})
    # messages.success(request, "Test success message")
    # messages.warning(request, "Test warning message")
    # messages.error(request, "Test error message")
    return response


def weekly_topic(request, topic):
    ctx = weekly.topic_context(topic)
    response = __weekly_topic_subscribe_form(request, topic, ctx)
    if response:
        return response
    response = render(request, "web/weekly_topic.html", {"ctx": ctx})
    return response


def weekly_topic_week(request, topic, year, week):
    ctx = weekly.topic_week_context(topic, year, week)
    response = __weekly_topic_subscribe_form(request, topic, ctx)
    if response:
        return response
    response = render(request, "web/weekly_topic_week.html", {"ctx": ctx})
    return response


def statistics(request):
    ctx = {"statistics": models.Statistics.all_statistics()}
    return render(request, "web/statistics.html", {"ctx": ctx})


def __social_context(request):
    twitter_bots = []
    for topic_key, topic in topics.topics.items():
        if not topic.get("twitter"):
            continue
        bot_name = topic.get("twitter").get("account")
        if not bot_name:
            continue
        bot = {
            "link": f"https://twitter.com/{ bot_name }",
            "link_title": f"{ topic['name'] } Twitter bot",
            "nick": f"@{ bot_name }",
            "description": f"{ topic['short_description'] }",
        }
        twitter_bots.append(bot)

    mastodon_bots = []
    for topic_key, topic in topics.topics.items():
        if not topic.get("mastodon"):
            continue
        bot_name = topic.get("mastodon").get("account")
        if not bot_name:
            continue
        bot = {
            "link": mastodon.profile_url(bot_name),
            "link_title": f"{ topic['name'] } Mastodon bot",
            "nick": "@" + bot_name.split("@")[1],
            "description": f"{ topic['short_description'] }",
        }
        mastodon_bots.append(bot)

    return {"twitter_bots": twitter_bots, "mastodon_bots": mastodon_bots}


def social(request):
    ctx = __social_context(request)
    return render(request, "web/social.html", {"ctx": ctx})
