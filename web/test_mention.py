from web import models
from django.test import TestCase
from django.utils import timezone


class Mention(TestCase):
    def setUp(self):
        self.user = models.CustomUser.objects.create_user(
            username="jacob", email="jacob@…", password="top_secret"
        )

    def test_rules(self):
        r = models.Mention.objects.create(
            user=self.user,
            rule_name="r1",
            url_pattern="https://xojoc.pw",
            title_pattern="",
            platforms=["r"],
            subreddits_only=["programming"],
            min_comments=4,
            min_score=3,
        )

        d = models.Discussion.objects.create(
            platform_id="h123",
            created_at=timezone.now(),
            scheme_of_story_url="https",
            schemeless_story_url="xojoc.pw",
            title="Alexandru Cojocaru",
            comment_count=10,
            score=20,
            tags=["programming"],
        )

        print(r.pk)
        print(d.pk)
        # self.assertIsNotNone(r.mentionnotification)
