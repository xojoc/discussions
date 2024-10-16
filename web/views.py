# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import itertools
import json
import logging
import random
from pprint import pformat
from urllib.parse import quote, unquote as url_unquote

import crispy_forms
import crispy_forms.layout
import stripe
import stripe.error
import urllib3
from crawlerdetect import CrawlerDetect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponsePermanentRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_htmx.middleware import HtmxDetails
from django_redis import get_redis_connection

from discussions import settings
from web import email_util, mention, spam
from web.platform import Platform

from . import (
    forms,
    mastodon,
    models,
    reading_list,
    topics,
    util,
    weekly,
)

logger = logging.getLogger(__name__)


class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


def __log_query(q):
    if not q:
        return

    q = q.strip().lower()

    try:
        r = get_redis_connection()
        if q.startswith(("http://", "https://")):
            r.zincrby("discussions:stats:query:url", 1, q)
        else:
            r.zincrby("discussions:stats:query:search", 1, q)

        if random.randint(1, 100) == 1:  # noqa: S311
            r.zremrangebyrank("discussions:stats:query:url", 0, -10)
            r.zremrangebyrank("discussions:stats:query:search", 0, -10)
    except Exception:  # noqa: BLE001
        logger.warning("__log_query failed", exc_info=True)


def discussions_context_cached(q):
    if util.is_dev():
        return discussions_context(q)

    if not q:
        return discussions_context(q)

    suffix = (q or "").lower().strip()

    key = "discussions_context:" + suffix
    touch_key = "touch:" + key
    ctx = cache.get(key)

    timeout = 5 * 60

    if ctx:
        if cache.get(touch_key):
            _ = cache.touch(key, timeout)
    else:
        ctx = discussions_context(q)
        if ctx and ctx["nothing_found"] is False:
            cache.set(key, ctx, timeout)
            cache.set(touch_key, 1, 3 * timeout)

    return ctx


def discussions_context(q):
    ctx = {}
    q = (q or "").strip()
    url = (q or "").lower().strip()

    if url and not (url.startswith(("http://", "https://"))):
        ctx["absolute_url"] = "https://" + q
    else:
        ctx["absolute_url"] = q

    ctx["link_canonical_url"] = util.discussions_canonical_url(q)

    ctx["original_query"] = q
    ctx["url"] = url
    min_url_len = len("http://" + "d" + ".it")
    if (
        (url.startswith(("http://", "https://")))
        and " " not in url
        and len(url) >= min_url_len
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
    uds, cu, _ = models.Discussion.of_url_or_title(ctx["url"])

    ctx["sql_query"] = ""
    if uds is not None:
        ctx["sql_query"] = str(uds.query)

    uds = list(uds) if uds else []

    tds = None

    ctx["canonical_url"] = cu

    ctx["discussions"] = uds
    ctx["title_discussions"] = tds

    uds.sort(key=lambda i: i.platform)

    # We have to convert the iterator to a list, see: https://stackoverflow.com/a/16171518
    ctx["grouped_discussions"] = [
        (
            Platform(platform),
            Platform(platform).label,
            Platform(platform).url,
            Platform(platform).tag_url,
            list(uds),
        )
        for platform, uds in itertools.groupby(uds, lambda x: x.platform)
    ]

    #    q.startswith('https://'):

    ctx["resource"] = models.Resource.by_url(cu)
    if ctx["resource"]:
        ctx["title"] = ctx["resource"].title
        ctx["inbound_resources"] = ctx["resource"].inbound_resources()[:20]
        ctx["outbound_resources"] = ctx["resource"].outbound_resources()[:20]

    if not ctx.get("title"):
        if uds and (q.startswith(("http://", "https://"))):
            ctx["title"] = uds[0].title
        else:
            ctx["title"] = ctx["original_query"]

    if not uds and not ctx.get("inbound_resources"):
        ctx["display_discussions"] = False

    if not uds and not tds and not ctx.get("inbound_resources"):
        ctx["nothing_found"] = True

    return ctx


def __get_submit_links(request, ctx):
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
        "Twitter": f"https://twitter.com/intent/tweet?url={url}&text={t}",
        "Mastodon": f"https://mastodon.social/share?text={t}%0A{url}",
    }

    ctx["submit_links"] = submit_links

    ctx["submit_links_visible"] = False
    if ctx["nothing_found"]:
        ctx["submit_links_visible"] = True


def __try_with(request, ctx):
    if ctx.get("is_url"):
        url = ctx.get("url", "")
        try:
            u = urllib3.util.parse_url(url)
            if u.host:
                ctx["try_with_site_prefix"] = "site:" + u.host
        except ValueError:
            logger.warning("Failed to parse url %", url, exc_info=True)

    if ctx.get("submit_title") and not ctx.get("submit_title", "").startswith(
        (
            "http://",
            "https://",
        ),
    ):
        ctx["try_with_title"] = ctx.get("submit_title")

    if (
        request.GET.get("submit_url", "")
        .lower()
        .startswith(("http://", "https://", "ftp://"))
    ):
        ctx["try_with_url"] = request.GET.get("submit_url")


def __suggest_topic(ctx):
    if ctx.get("is_url"):
        filtered_topics = []
        for d in ctx.get("discussions", []):
            for ftk, ft in topics.topics.items():
                if not ft.get("tags"):
                    continue
                if ftk == "programming":
                    continue
                if set(d.normalized_tags) & ft.get("tags"):
                    filtered_topics.append(ft)

        if len({ft["topic_key"] for ft in filtered_topics}) == 1:
            ft = filtered_topics[0]
            ctx["suggested_topic"] = ft["topic_key"]
            ctx["suggested_topic_name"] = ft["name"]
            ctx["suggested_topic_short_description"] = ft["short_description"]


def index(request: HttpRequest, path_q: str | None = None) -> HttpResponse:
    host = request.get_host().partition(":")[0]
    if not request.path.startswith("/.well-known/") and (
        host
        not in {"localhost", "127.0.0.1", "testserver", settings.APP_DOMAIN}
    ):
        r = "https://" + settings.APP_DOMAIN + request.get_full_path()
        return HttpResponsePermanentRedirect(r)

    if path_q:
        q = url_unquote(request.get_full_path()[len("/q/") :])
    else:
        q = request.GET.get("url") or request.GET.get("q")

    q = q or ""

    if (
        path_q
        and q.startswith("http:/")
        and not q.startswith("http://")
        and " " not in q
    ):
        p = request.get_full_path().replace("http:/", "http://", 1)
        return redirect(request.build_absolute_uri(p))

    if (
        path_q
        and q.startswith("https:/")
        and not q.startswith("https://")
        and " " not in q
    ):
        p = request.get_full_path().replace("https:/", "https://", 1)
        return redirect(request.build_absolute_uri(p))

    ctx = discussions_context_cached(q)

    __get_submit_links(request, ctx)
    __try_with(request, ctx)
    __suggest_topic(ctx)
    __log_query(q)

    response = render(request, "web/discussions.html", {"ctx": ctx})

    if ctx["nothing_found"]:
        response.status_code = 404

    return response


def short_url(request, platform_id):
    _ = request
    d = get_object_or_404(models.Discussion, pk=platform_id)
    redirect_to = reverse("web:index", args=[d.story_url])
    return redirect(redirect_to, permanent=False)


def story_short_url(request, platform_id):
    _ = request
    d = get_object_or_404(models.Discussion, pk=platform_id)
    return redirect(d.story_url or reverse("web:index"), permanent=False)


# def short_link(request, code):


def weekly_confirm_email(request):
    topic = request.GET.get("topic")
    subscriber_email = request.GET.get("email")
    try:
        subscriber = models.Subscriber.objects.get(
            topic=topic,
            email=subscriber_email,
        )
    except models.Subscriber.DoesNotExist:
        subscriber = None

    if subscriber and subscriber.confirmed and not subscriber.unsubscribed:
        messages.warning(
            request,
            (
                f"Email {subscriber_email} was already confirmed. "
                f"If it wasn't you please write to hi@discu.eu"
            ),
        )
    elif subscriber and subscriber.verification_code == request.GET.get(
        "verification_code",
    ):
        subscriber.subscribe()
        subscriber.save()

        messages.success(
            request,
            f"Email {subscriber_email} confirmed. Thank you!",
        )
    else:
        messages.error(
            request,
            (
                f"Something went wrong while trying to confirm email "
                f"{subscriber_email}. Write to hi@discu.eu for assistance."
            ),
        )

    redirect_to = "/"
    if topic:
        redirect_to = reverse("web:weekly_topic", args=[topic])
    else:
        redirect_to = reverse("web:weekly_index")

    return redirect(redirect_to, permanent=False)


def weekly_confirm_unsubscription(request):
    if request.method == "GET":
        topic = request.GET.get("topic")
        subscriber_email = request.GET.get("email")
        try:
            subscriber = models.Subscriber.objects.get(
                topic=topic,
                email=subscriber_email,
            )
        except models.Subscriber.DoesNotExist:
            subscriber = None

        form = forms.UnsubscribeForm(request.GET, instance=subscriber)
        topic_key = request.GET.get("topic")
        ctx = {
            "weekly_unsubscribe_form": form,
            "topic": topics.topics.get(topic_key),
        }
        return render(
            request,
            "web/weekly_unsubscribe_page.html",
            {"ctx": ctx},
        )

    if request.method == "POST":
        topic = request.POST.get("topic")
        subscriber_email = request.POST.get("email")
        verification_code = request.POST.get("verification_code")

        try:
            subscriber = models.Subscriber.objects.get(
                topic=topic,
                email=subscriber_email,
            )
        except models.Subscriber.DoesNotExist:
            subscriber = None

        if subscriber and subscriber.verification_code != verification_code:
            messages.error(
                request,
                (
                    "Something went wrong. Verification code doesn't match. "
                    "Write to hi@discu.eu for assistance."
                ),
            )
        elif (
            subscriber and subscriber.confirmed and not subscriber.unsubscribed
        ):
            subscriber.unsubscribe()
            subscriber.unsubscribed_feedback = request.POST.get(
                "unsubscribed_feedback",
            )
            subscriber.save()
            messages.success(request, "You're now unsubscribed. Thank you!")
        else:
            messages.warning(
                request,
                (
                    "You were already unsubscribed. "
                    "Write to hi@discu.eu for assistance."
                ),
            )

        redirect_to = "/"
        if topic:
            redirect_to = reverse("web:weekly_topic", args=[topic])
        else:
            redirect_to = reverse("web:weekly_index")

        return redirect(redirect_to, permanent=False)
    return None


def __weekly_topic_subscribe_form(request, topic, ctx):
    subscriber = None
    if request.POST:
        try:
            subscriber = models.Subscriber.objects.get(
                topic=request.POST.get("topic"),
                email=request.POST.get("email"),
            )
        except models.Subscriber.DoesNotExist:
            subscriber = None

    form = forms.SubscriberForm(
        request.POST or None,
        instance=subscriber,
        initial={"topic": topic},
    )

    if form.is_valid():
        subscriber = form.save()
        subscriber.http_headers = dict(request.headers)
        subscriber.save()

        if spam.is_form_spammer(request, form):
            subscriber.delete()
        elif subscriber.suspected_spam:
            email_util.send_admins(
                "Suspected spammer",
                f"""
Suspected spammer:
{pformat(subscriber)}

Headers:
{pformat(request.META, sort_dicts=True)}
""",
            )
        else:
            subscriber.send_confirmation_email()

        messages.success(
            request,
            f"Thank you! A confirmation email was sent to {subscriber.email}.",
        )

    ctx["weekly_subscribe_form"] = form


def weekly_index(request):
    ctx = weekly.index_context()
    response = __weekly_topic_subscribe_form(request, None, ctx)
    if response:
        return response
    return render(request, "web/weekly_index.html", {"ctx": ctx})


def weekly_topic(request, topic):
    if topic == "scheme":
        topic = "lisp"
    ctx = weekly.topic_context(topic)
    if not ctx:
        msg = "404"
        raise Http404(msg)

    response = __weekly_topic_subscribe_form(request, topic, ctx)
    if response:
        return response
    return render(request, "web/weekly_topic.html", {"ctx": ctx})


# @cache_page(24 * 60 * 60, key_prefix="weekly:")
def weekly_topic_week(request, topic, year, week):
    ctx = weekly.topic_week_context_cached(topic, year, week)
    if not ctx:
        msg = "404"
        raise Http404(msg)
    response = __weekly_topic_subscribe_form(request, topic, ctx)
    if response:
        return response
    return render(request, "web/weekly_topic_week.html", {"ctx": ctx})


def statistics(request):
    ctx = {"statistics": models.Statistics.all_statistics()}
    return render(request, "web/statistics.html", {"ctx": ctx})


def __social_context(request):
    _ = request
    twitter_bots = []
    for topic_key, topic in topics.topics.items():
        if topic_key == "laarc":
            continue
        if not topic.get("twitter"):
            continue
        bot_name = topic.get("twitter").get("account")
        if not bot_name:
            continue
        bot = {
            "link": f"https://twitter.com/{bot_name}",
            "link_title": f"{topic['name']} Twitter bot",
            "nick": f"@{bot_name}",
            "description": f"{topic['short_description']}",
        }
        twitter_bots.append(bot)

    mastodon_bots = []
    for topic_key, topic in topics.topics.items():
        if topic_key == "laarc":
            continue
        if not topic.get("mastodon"):
            continue
        bot_name = topic.get("mastodon").get("account")
        if not bot_name:
            continue
        bot = {
            "link": mastodon.profile_url(bot_name),
            "link_title": f"{topic['name']} Mastodon bot",
            "nick": "@" + bot_name.split("@")[1],
            "description": f"{topic['short_description']}",
        }
        mastodon_bots.append(bot)

    return {"twitter_bots": twitter_bots, "mastodon_bots": mastodon_bots}


def social(request):
    ctx = __social_context(request)
    return render(request, "web/social.html", {"ctx": ctx})


@login_required
def dashboard(request):
    ctx = {}

    profile_form = forms.ProfileForm(instance=request.user)
    if (
        request.method == "POST"
        and "submit-update-user-profile" in request.POST
    ):
        profile_form = forms.ProfileForm(
            request.POST,
            instance=request.user,
        )
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Profile updated successfully!")

    ctx["profile_form"] = profile_form

    user_emails = request.user.emailaddress_set.filter(
        verified=True,
    ).values_list("email", flat=True)
    subscriptions = models.Subscriber.objects.filter(
        email__in=user_emails,
    ).order_by("topic")
    ctx["subscriptions"] = subscriptions

    ctx["user_verified_email"] = (
        request.user.emailaddress_set.filter(primary=True)
        .filter(verified=True)
        .exists()
    )

    if not ctx["user_verified_email"]:
        messages.warning(
            request,
            "Please verify your email to access all the features.",
        )

    ctx["topics"] = topics.topics

    return render(request, "web/dashboard.html", {"ctx": ctx})


@login_required
def dashboard_mentions(request):
    ctx = {}

    mention_form = forms.MentionForm()

    if request.method == "POST":
        if "submit-new-mention-rule" in request.POST:
            mention_form = forms.MentionForm(request.POST)
            mrc = request.user.mention_set.all().filter(disabled=False).count()
            mrm = request.user.max_mention_rules()
            if mrc >= mrm:
                messages.error(
                    request,
                    (
                        "Sorry, but you already reached your "
                        "maximum quota of rules"
                    ),
                )
            elif mention_form.is_valid():
                model = mention_form.save(commit=False)
                model.user = request.user
                model.save()
                messages.success(
                    request,
                    f"Rule {model} saved!",
                )
                mention_form = forms.MentionForm()
                return redirect(request.get_full_path(), permanent=False)

        if "submit-delete-mention-rule" in request.POST:
            pk = request.POST["mention-rule-delete-pk"]
            mention = get_object_or_404(models.Mention, pk=pk)
            if mention.user != request.user:
                msg = "404"
                raise Http404(msg)
            _ = mention.delete()
            messages.success(request, f"Rule {mention} deleted!")
            return redirect(request.get_full_path(), permanent=False)

    ctx["mention_form"] = mention_form

    ctx["mentions"] = request.user.mention_set.all()

    return render(request, "web/dashboard_mentions.html", {"ctx": ctx})


@login_required
def dashboard_mentions_edit(request, pk):
    ctx = {}
    mention = get_object_or_404(models.Mention, pk=pk)
    if mention.user != request.user:
        msg = "404"
        raise Http404(msg)

    # if mention.disabled:

    edit_form = forms.EditMentionForm(instance=mention)

    if request.method == "POST":
        edit_form = forms.EditMentionForm(request.POST, instance=mention)

        if "submit-edit-mention-rule" in request.POST:
            logger.info("b")
            if edit_form.is_valid():
                logger.info("c")
                model = edit_form.save()
                messages.success(
                    request,
                    f"Rule {model} saved!",
                )
                return redirect(
                    reverse("web:dashboard_mentions"),
                    permanent=False,
                )

    ctx["form"] = edit_form
    ctx["mention"] = mention

    return render(request, "web/dashboard_mentions_edit.html", {"ctx": ctx})


@require_http_methods(["POST"])
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user = models.CustomUser.objects.get(pk=session.client_reference_id)
        user.premium_active = True
        user.premium_active_from = timezone.now()
        user.premium_cancelled = False
        user.premium_cancelled_on = None
        user.stripe_customer_id = session.customer
        user.save()

    if event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        user = models.CustomUser.objects.get(
            stripe_customer_id=subscription.customer,
        )
        user.premium_active = False
        user.premium_cancelled = True
        user.premium_cancelled_on = timezone.now()
        user.save()

    return HttpResponse(status=200)


@login_required
@require_http_methods(["POST"])
def stripe_create_customer_portal_session(request):
    return_path = request.POST.get("return_to_path") or reverse(
        "web:dashboard",
    )
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return_url = f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}{return_path}"
    session = stripe.billing_portal.Session.create(
        customer=request.user.stripe_customer_id,
        return_url=return_url,
    )
    return redirect(session.url, permanent=False)


@login_required
@require_http_methods(["POST"])
def stripe_checkout(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    price_id = settings.STRIPE_PLAN_PRICE_API_ID
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        automatic_tax={"enabled": True},
        client_reference_id=request.user.id,
        customer=request.user.stripe_customer_id,
        customer_update={"address": "auto", "name": "auto"},
        success_url=(
            f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}/stripe/subscribe/success/?stripe_session_id="
            f"{{CHECKOUT_SESSION_ID}}"
        ),
        cancel_url=f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}/stripe/subscribe/cancel/",
    )
    return redirect(session.url, permanent=False)


def stripe_subscribe_success(request):
    messages.success(request, "Thank you! You're now a premium user!")
    return redirect("web:dashboard", permanent=False)


def stripe_subscribe_cancel(request):
    messages.warning(
        request,
        (
            "Oops. Something went wrong. No worries you can retry later "
            "or write to hi@discu.eu for support"
        ),
    )
    logger.error(
        "Stripe subscribe cancelled. User % stripe id %",
        request.user.pk,
        request.user.stripe_customer_id,
    )
    return redirect("web:dashboard", permanent=False)


def new_ad(request):
    ctx = {}
    ctx["htmx"] = request.htmx
    template = "web/new_ad.html"
    if request.htmx:
        template = "web/new_ad_form.html"

    if request.method == "POST":
        ad_form = forms.ADForm(request.POST)
        if ad_form.is_valid():
            if "simulate-new-ad" in request.POST or request.htmx:
                ctx["estimate"] = ad_form.instance.estimate()
            else:
                model = ad_form.save(commit=False)
                model.user = request.user
                model.save()
                messages.success(
                    request,
                    f"""Thank you!
                    Total price is {model.estimated_total_euro}€
                    We'll let you know once the ad is approved.""",
                )
                email_util.send_admins("New ad", "new ad")
    else:
        ad_form = forms.ADForm()

    ctx["user_verified_email"] = (
        request.user.is_authenticated
        and request.user.emailaddress_set.filter(primary=True)
        .filter(verified=True)
        .exists()
    )

    if ctx["user_verified_email"]:
        ad_form.helper.add_input(
            crispy_forms.layout.Submit(
                "submit-new-ad",
                "Submit ad",
                css_class="btn btn-primary",
            ),
        )

    ctx["ad_form"] = ad_form

    return render(request, template, {"ctx": ctx})


def reading_list_topic(request, topic):
    ctx = {}
    ctx["topic"] = topics.topics.get(topic)
    if not ctx["topic"]:
        msg = "not found"
        raise Http404(msg)

    ctx["articles"] = reading_list.get_reading_list_cached(topic, "article")

    return render(request, "web/reading_list_topic.html", {"ctx": ctx})


def api_view(request):
    ctx = {}
    ctx["statistics"] = models.Statistics.all_statistics()
    exclude_platforms = {
        Platform.TILDE_NEWS,
        Platform.BARNACLES,
        Platform.LAARC,
        Platform.STANDARD,
    }
    ctx["statistics"]["platform"] = [
        p
        for p in ctx["statistics"]["platform"]
        if p["platform"] not in exclude_platforms
    ]

    return render(request, "web/api.html", {"ctx": ctx})


def mentions(request):
    ctx = {}

    return render(request, "web/mentions.html", {"ctx": ctx})


@csrf_exempt
def aws_bounce_handler(request):
    if request.body.decode("utf-8"):
        unsubscribe = False
        destinations = []

        message = json.loads(json.loads(request.body)["Message"])
        notification_type = message.get("notificationType")
        if notification_type == "Bounce":
            bounce = message.get("bounce")
            if bounce.get("bounceType") in {"Undetermined", "Permanent"}:
                unsubscribe = True
            destinations = [
                recipient.get("emailAddress")
                for recipient in bounce.get("bouncedRecipients")
            ]
        elif notification_type == "Complaint":
            unsubscribe = True
            complaint = message.get("complaint")
            destinations = [
                recipient.get("emailAddress")
                for recipient in complaint.get("complainedRecipients")
            ]

        if unsubscribe:
            from_email = message.get("mail").get("source")
            topic_key, _ = topics.get_topic_by_email(from_email) or ("", "")
            for destination in destinations:
                subscriber = models.Subscriber.objects.filter(
                    topic=topic_key,
                    email=destination,
                ).first()
                if not subscriber:
                    continue

                subscriber.unsubscribe()
                subscriber.aws_notification = request.body.decode("utf-8")
                subscriber.unsubscribed_from = "aws"
                subscriber.save()

    return JsonResponse({})


@csrf_exempt
@login_required
def mention_live_preview(request):
    ctx = {}
    rule = json.loads(request.body.decode("utf-8"))
    rule_form = forms.MentionForm(rule)
    ctx["errors"] = rule_form.errors
    ctx["form"] = rule_form
    ctx["discussions"] = []
    if rule_form.is_valid():
        rule_model = rule_form.save(commit=False)
        ctx["discussions"] = mention.discussions(rule_model) or []

    ctx["discussions"] = ctx["discussions"][:10]

    return render(
        request,
        "web/dashboard_mentions_live_preview.html",
        {"ctx": ctx},
    )


def click(request):
    url = request.GET.get("url")
    if not url:
        msg = "404"
        raise Http404(msg)
    sub = request.GET.get("subscriber")
    year = request.GET.get("year")
    week = request.GET.get("week")

    crawler_detect = CrawlerDetect(headers=request.headers)
    is_crawler = crawler_detect.isCrawler()

    if not is_crawler and sub:
        try:
            subscriber = models.Subscriber.objects.get(pk=sub)
        except models.Subscriber.DoesNotExist:
            subscriber = None
        if subscriber:
            subscriber.clicked(year, week)
            subscriber.save()

    return redirect(url, permanent=False)


def click_subscriber(request, typ, subscriber, year, week, discussion):
    crawler_detect = CrawlerDetect(headers=request.headers)
    is_crawler = crawler_detect.isCrawler()

    if not is_crawler:
        try:
            subscriber = models.Subscriber.objects.get(pk=subscriber)
        except models.Subscriber.DoesNotExist:
            subscriber = None
        if subscriber:
            subscriber.clicked(year, week)
            subscriber.save()

    discussion = get_object_or_404(models.Discussion, pk=discussion)

    if typ == "d":
        return redirect(
            reverse("web:index", args=[discussion.story_url]),
            permanent=False,
        )
    return redirect(
        discussion.story_url or reverse("web:index"),
        permanent=False,
    )
