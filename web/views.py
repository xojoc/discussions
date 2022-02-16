from . import models, discussions, twitter, util, forms
from . import mastodon, weekly, email
from django.shortcuts import render, redirect
from django.urls import reverse
import itertools
from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect
from discussions import settings
from urllib.parse import unquote as url_unquote
from urllib.parse import quote
import logging
from django_redis import get_redis_connection
import urllib3
from django.contrib import messages
import django.template.loader as template_loader
import urllib

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
    ctx["is_url"] = url.startswith("http://") or url.startswith("https://")
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
            models.Discussion.platform_name(platform),
            models.Discussion.platform_url(
                platform,
                preferred_external_url=discussions.PreferredExternalURL.Standard,
            ),
            models.Discussion.platform_tag_url(
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
    if not (
        q.lower().startswith("http://") or q.lower().startswith("https://")
    ):
        return

    url = quote(q)

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


def weekly_index(request):
    ctx = weekly.index_context()
    response = render(request, "web/weekly_index.html", {"ctx": ctx})
    return response


def weekly_confirm_email(request):
    topic = request.GET.get("topic")
    email = request.GET.get("email")
    try:
        subscriber = models.Subscriber.objects.get(topic=topic, email=email)
    except models.Subscriber.DoesNotExist:
        subscriber = None

    if subscriber and subscriber.confirmed:
        messages.warning(
            request,
            f"Email {email} was already confirmed. If it wasn't you please write to hi@discu.eu",
        )
    elif subscriber and subscriber.verification_code == request.GET.get(
        "verification_code"
    ):
        subscriber.confirmed = True
        subscriber.save()

        messages.success(request, f"Email {email} confirmed. Thank you!")
    else:
        messages.error(
            request,
            f"Something went wrong while trying to confirm email {email}. Write to hi@discu.eu for assistance.",
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
        topic = form.cleaned_data["topic"]
        subscriber_email = form.cleaned_data["email"]
        verification_code = subscriber.verification_code

        confirmation_url = (
            f"https://{settings.APP_DOMAIN}/weekly/confirm_email?"
            + urllib.parse.urlencode(
                [
                    ("topic", topic),
                    ("email", subscriber_email),
                    ("verification_code", verification_code),
                ]
            )
        )
        email.send(
            f"Confirm subscription to weekly {weekly.topics[topic]['name']} digest",
            template_loader.render_to_string(
                "web/weekly_subscribe_confirm.txt",
                {
                    "ctx": {
                        "topic": weekly.topics[topic],
                        "confirmation_url": confirmation_url,
                    }
                },
            ),
            weekly.topics[topic]["email"],
            subscriber_email,
        )

        messages.success(
            request,
            f"Thank you! A confirmation email was sent to {subscriber_email}.",
        )

    ctx["weekly_subscribe_form"] = form
    return None


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
    for bot_name, bot_values in twitter.configuration["bots"].items():
        bot = {
            "link": f"https://twitter.com/{ bot_name }",
            "link_title": f"{ bot_values['topic'] } Twitter bot",
            "nick": f"@{ bot_name }",
            "description": f"{ bot_values['description'] }",
        }
        twitter_bots.append(bot)

    mastodon_bots = []
    for bot_name, bot_values in twitter.configuration["bots"].items():
        bot = {
            "link": mastodon.profile_url(bot_values["mastodon_account"]),
            "link_title": f"{ bot_values['topic'] } Mastodon bot",
            "nick": "@" + bot_values["mastodon_account"].split("@")[1],
            "description": f"{ bot_values['description'] }",
        }
        mastodon_bots.append(bot)

    return {"twitter_bots": twitter_bots, "mastodon_bots": mastodon_bots}


def social(request):
    ctx = __social_context(request)
    return render(request, "web/social.html", {"ctx": ctx})
