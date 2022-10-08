import logging

import cleanurl
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from celery import shared_task

from web import models, title


logger = logging.getLogger(__name__)


def __process_mentions(sender, instance: models.Discussion, created, **kwargs):
    rules = (
        models.Mention.objects.filter(disabled=False)
        .filter(min_comments__lte=instance.comment_count)
        .filter(min_score__lte=instance.score)
        .filter(Q(platforms__contains=[instance.platform]) | Q(platforms=[]))
        .exclude(mentionnotification__discussion=instance)
    )

    matched_rules = []

    # breakpoint()

    story_title = title.normalize(instance.title, stem=False)

    for r in rules:
        if r.base_url:
            base_url = ""
            cu = cleanurl.cleanurl(r.base_url, generic=True, host_remap=False)
            if cu:
                base_url = cu.schemeless_url

            base_url_remapped = ""
            cu = cleanurl.cleanurl(r.base_url, generic=True, host_remap=True)
            if cu:
                base_url_remapped = cu.schemeless_url

            if not (
                (
                    base_url_remapped
                    and (
                        base_url_remapped == instance.canonical_story_url
                        or instance.canonical_story_url
                        and instance.canonical_story_url.startswith(
                            base_url_remapped + "/"
                        )
                    )
                )
                or (
                    base_url
                    and (
                        base_url == instance.schemeless_story_url
                        or instance.schemeless_story_url
                        and instance.schemeless_story_url.startswith(
                            base_url + "/"
                        )
                    )
                )
            ):
                continue

        # if r.url_pattern:
        #     pat = re.escape(r.url_pattern)
        #     pat = pat.replace("%", ".*")
        #     if not (
        #         re.match(
        #             pat, instance.canonical_story_url or "", re.IGNORECASE
        #         )
        #         or re.match(
        #             pat, instance.schemeless_story_url or "", re.IGNORECASE
        #         )
        #     ):
        #         continue

        # if r.title_pattern:
        #     pat = re.escape(r.title_pattern)
        #     pat = pat.replace("%", ".*")
        #     if not (re.match(pat, instance.title or "", re.IGNORECASE)):
        #         continue

        if r.keyword:
            keyword = title.normalize(r.keyword, stem=False)
            if keyword not in story_title.split():
                continue

        if instance.platform == "r":
            tags: list[str] = instance.tags or []
            if r.subreddits_only and tags[0] not in r.subreddits_only:
                continue
            if r.subreddits_exclude and tags[0] in r.subreddits_exclude:
                continue

        matched_rules.append(r)

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


@shared_task(bind=True, ignore_result=True)
def email_notification(self):

    return
