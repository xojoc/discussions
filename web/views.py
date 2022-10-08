import itertools
import logging
import random
from urllib.parse import quote
from urllib.parse import unquote as url_unquote

import stripe
import urllib3
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_redis import get_redis_connection

from discussions import settings

from . import (
    discussions,
    forms,
    mastodon,
    models,
    topics,
    util,
    weekly,
    reading_list,
)

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

    if random.randint(1, 100) == 1:
        r.zremrangebyrank("discussions:stats:query:url", 0, -10)
        r.zremrangebyrank("discussions:stats:query:search", 0, -10)


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
        "Twitter": f"https://twitter.com/intent/tweet?url={url}&text={t}",
        "Mastodon": f"https://mastodon.social/share?text={t}%0A{url}",
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

    get_submit_links(request, ctx)

    if ctx.get("is_url"):
        url = ctx.get("url", "")
        try:
            u = urllib3.util.parse_url(url)
            if u.host:
                ctx["try_with_site_prefix"] = "site:" + u.host
        except Exception as e:
            logger.info(e)

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

    # messages.debug(request, "debug")
    # messages.info(request, "info")
    # messages.success(request, "success")
    # messages.warning(request, "warning")
    # messages.error(request, "error")

    return response


def short_url(request, platform_id):
    d = get_object_or_404(models.Discussion, pk=platform_id)
    redirect_to = reverse("web:index", args=[d.story_url])
    return redirect(redirect_to, permanent=False)


def story_short_url(request, platform_id):
    d = get_object_or_404(models.Discussion, pk=platform_id)
    return redirect(d.story_url, permanent=False)


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
        topic = request.GET.get("topic")
        subscriber_email = request.GET.get("email")
        try:
            subscriber = models.Subscriber.objects.get(
                topic=topic, email=subscriber_email
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
        request.POST or None, instance=subscriber, initial={"topic": topic}
    )

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
    if not ctx:
        raise Http404("404")

    response = __weekly_topic_subscribe_form(request, topic, ctx)
    if response:
        return response
    response = render(request, "web/weekly_topic.html", {"ctx": ctx})
    return response


# @cache_page(24 * 60 * 60, key_prefix="weekly:")
def weekly_topic_week(request, topic, year, week):
    ctx = weekly.topic_week_context_cached(topic, year, week)
    if not ctx:
        raise Http404("404")
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


@login_required
def dashboard(request):
    ctx = {}

    profile_form = forms.ProfileForm(instance=request.user)
    mention_form = forms.MentionForm()

    if request.method == "POST":
        if "submit-update-user-profile" in request.POST:
            profile_form = forms.ProfileForm(
                request.POST, instance=request.user
            )
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated successfully!")

        if "submit-new-mention-rule" in request.POST:
            mention_form = forms.MentionForm(request.POST)
            if mention_form.is_valid():
                model = mention_form.save(commit=False)
                model.user = request.user
                model.save()
                messages.success(
                    request,
                    f"Rule {model} saved!",
                )

    ctx["profile_form"] = profile_form
    ctx["mention_form"] = mention_form

    user_emails = request.user.emailaddress_set.filter(
        verified=True
    ).values_list("email", flat=True)
    subscriptions = models.Subscriber.objects.filter(
        email__in=user_emails
    ).order_by("topic")
    ctx["subscriptions"] = subscriptions

    ctx["user_verified_email"] = (
        request.user.emailaddress_set.filter(primary=True)
        .filter(verified=True)
        .exists()
    )

    if not ctx["user_verified_email"]:
        messages.warning(
            request, "Please verify your email to access all the features."
        )

    ctx["topics"] = topics.topics

    return render(request, "web/dashboard.html", {"ctx": ctx})


@require_http_methods(["POST"])
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
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
            stripe_customer_id=subscription.customer
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
        "web:dashboard"
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
        success_url=f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}/stripe/subscribe/success/?stripe_session_id="
        + "{{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}/stripe/subscribe/cancel/",
    )
    return redirect(session.url, permanent=False)


def stripe_subscribe_success(request):
    messages.success(request, "Thank you! You're now a premium user!")
    return redirect("web:dashboard", permanent=False)


def stripe_subscribe_cancel(request):
    messages.warning(
        request,
        "Oops. Something went wrong. No worries you can retry later or write to hi@discu.eu for support",
    )
    logger.error(
        f"Stripe subscribe cancelled. User {request.user.pk} stripe id {request.user.stripe_customer_id}"
    )
    return redirect("web:dashboard", permanent=False)


def new_ad(request):
    ctx = {}

    ad_form = forms.ADForm()
    simulate_ad_form = forms.SimulateADForm()

    if request.method == "POST":
        if "submit-new-ad" in request.POST:
            ad_form = forms.ADForm(request.POST)
            if ad_form.is_valid():
                model = ad_form.save(commit=False)
                model.user = request.user
                model.save()
                messages.success(
                    request,
                    f"""Thank you!
                    Total price is {model.estimated_total_euro}€
                    We'll let you know once the ad is approved.""",
                )

        if "simulate-new-ad" in request.POST:
            simulate_ad_form = forms.SimulateADForm(request.POST)
            if simulate_ad_form.is_valid():
                ctx["estimate"] = simulate_ad_form.instance.estimate()

            ad_form = forms.ADForm(request.POST)

    ctx["ad_form"] = ad_form
    ctx["simulate_ad_form"] = simulate_ad_form

    ctx["user_verified_email"] = (
        request.user.is_authenticated
        and request.user.emailaddress_set.filter(primary=True)
        .filter(verified=True)
        .exists()
    )
    return render(request, "web/new-ad.html", {"ctx": ctx})


def reading_list_topic(request, topic):
    ctx = {}
    ctx["topic"] = topics.topics.get(topic)
    if not ctx["topic"]:
        raise Http404("not found")

    ctx["articles"] = reading_list.get_reading_list_cached(topic, "article")

    return render(request, "web/reading_list_topic.html", {"ctx": ctx})
