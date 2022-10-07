import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from web import models

logger = logging.getLogger(__name__)


@receiver(post_save, sender=models.Discussion)
def process_mentions(sender, instance: models.Discussion, created, **kwargs):
    rules = (
        models.Mention.objects.filter(disabled=False)
        .filter(min_comments__lte=instance.comment_count)
        .filter(min_score__lte=instance.score)
        .filter(platforms__contains=[instance.platform])
        .exclude(mentionnotification__discussion=instance)
    )

    matched_rules = []

    for r in rules:
        if r.title_pattern not in instance.normalized_title:
            continue

        if r.url_pattern not in instance.canonical_story_url:
            continue

        if instance.platform == "r":
            if r.subreddits_only and instance.tags[0] not in r.subreddits_only:
                continue
            if (
                r.subreddits_exclude
                and instance.tags[0] in r.subreddits_exclude
            ):
                continue

        matched_rules.append(r)

    for r in matched_rules:
        models.MentionNotification.objects.create(
            mention=r,
            discussion=instance,
        )
