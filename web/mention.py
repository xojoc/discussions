# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import datetime
import logging
import re
from email.utils import formataddr
from functools import reduce
from operator import or_

import cleanurl
import django.template.loader as template_loader
from celery import shared_task
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from web import email_util, models, title

logger = logging.getLogger(__name__)


def discussions(rule: models.Mention, pk=None):
    keywords = rule.keywords or []
    if rule.keyword and not rule.keywords:
        keywords = [rule.keyword]
    for i, k in enumerate(keywords):
        keywords[i] = title.normalize(k, stem=False)

    rurl = rule.base_url or ""
    if rurl:
        rurl = "//" + rurl

    cu = cleanurl.cleanurl(rurl, generic=True, host_remap=False)
    base_url = rule.base_url or ""
    if cu:
        base_url = cu.schemeless_url

    cbase_url = ""
    ccu = cleanurl.cleanurl(rurl)
    if ccu:
        cbase_url = ccu.schemeless_url

    subreddits_exclude = rule.subreddits_exclude or []

    ago = timezone.now() - datetime.timedelta(days=365)

    ds = (
        models.Discussion.objects.filter(comment_count__gte=rule.min_comments)
        .filter(score__gte=rule.min_score)
        .exclude(_platform__in=(rule.exclude_platforms or []))
        .filter(created_at__gt=ago)
    )

    if base_url:
        q_filter = Q(schemeless_story_url__startswith=rule.base_url) | Q(
            canonical_story_url__startswith=rule.base_url,
        )

        q_filter = (
            q_filter
            | Q(schemeless_story_url__startswith=base_url)
            | Q(canonical_story_url__startswith=base_url)
        )

        if cbase_url:
            q_filter = (
                q_filter
                | Q(schemeless_story_url__startswith=cbase_url)
                | Q(canonical_story_url__startswith=cbase_url)
            )

        ds = ds.filter(q_filter)

    if keywords:
        ds = ds.filter(
            reduce(or_, [Q(normalized_title__icontains=k) for k in keywords]),
        )

    if pk:
        ds = ds.filter(pk=pk)

    if subreddits_exclude:
        ds = ds.exclude(Q(_platform="r") & Q(tags__overlap=subreddits_exclude))

    dsa = []

    for d in ds.order_by("-created_at")[:15]:
        if not keywords:
            dsa.append(d)
            continue

        ok = False
        for k in keywords:
            if re.search(r"\b" + k + r"\b", d.normalized_title or ""):
                ok = True
                break
            if re.search(
                r"\b" + k + r"\b",
                " ".join((d.title or "").lower().split()),
            ):
                ok = True
                break

        if ok:
            dsa.append(d)
            continue

    return dsa


def __rule_matches(rule: models.Mention, instance: models.Discussion):
    return discussions(rule, instance.pk)

    # if rule.base_url:
    #     if not instance.story_url:

    #     if cu:

    #     if cu:

    #     if not (
    #             base_url_remapped
    #             and (
    #                 or instance.canonical_story_url
    #                 and instance.canonical_story_url.startswith(
    #                     base_url_remapped + "/"
    #         or (
    #             base_url
    #             and (
    #                 or instance.schemeless_story_url
    #                 and instance.schemeless_story_url.startswith(
    #                     base_url + "/"
    #     ):

    # if rule.keyword:
    #     if not keyword_set.issubset(set(story_title.split())):

    # if instance.platform == "r":
    #     if rule.subreddits_exclude and tags[0] in rule.subreddits_exclude:


def __matching_rules(instance: models.Discussion):
    rules = (
        models.Mention.objects.filter(disabled=False)
        .filter(min_comments__lte=instance.comment_count)
        .filter(min_score__lte=instance.score)
        .exclude(exclude_platforms__contains=[instance.platform])
        .exclude(mentionnotification__discussion=instance)
    )

    matched_rules = []

    for r in rules:
        if discussions(r, instance.pk):
            matched_rules.append(r)

    return matched_rules


def __process_mentions(sender, instance: models.Discussion, created, **kwargs):
    three_days_ago = timezone.now() - datetime.timedelta(days=3)
    if not instance.created_at:
        return

    if instance.created_at < three_days_ago:
        return

    matched_rules = __matching_rules(instance)

    for r in matched_rules:
        models.MentionNotification.objects.create(
            mention=r,
            discussion=instance,
        )


@receiver(post_save, sender=models.Discussion)
def process_mentions(sender, instance: models.Discussion, created, **kwargs):
    try:
        __process_mentions(sender, instance, created, **kwargs)
    except Exception as e:
        logger.error(f"Process mentions: {e}")


def __render_mention_notification(m):
    ctx = {
        "user": m.mention.user,
        "discussions": [m.discussion],
        "discussion": m.discussion,
        "mention_rule": m.mention,
    }
    return template_loader.render_to_string(
        "web/mention_email_digest.txt",
        {"ctx": ctx},
    )


@shared_task(bind=True, ignore_result=True)
def email_notification(self):
    mentions = (
        models.MentionNotification.objects.filter(email_sent=False)
        .exclude(discussion__isnull=True)
        .exclude(mention__isnull=True)
        .exclude(mention__user__isnull=True)
        .order_by("entry_created_at")
    )

    for m in mentions:
        if not m.discussion:
            continue
        if not m.mention.user:
            continue

        if m.mention.user.notifications_sent(15) >= 3:
            continue

        text_content = __render_mention_notification(m)

        email_util.send(
            f"[Discu] New discussion for you ({m.mention})",
            text_content,
            formataddr(("Discu Mentions", "mentions@discu.eu")),
            m.mention.user.email,
        )
        m.email_sent = True
        m.email_sent_at = timezone.now()
        m.save()
