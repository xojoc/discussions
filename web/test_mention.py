from web import models
from django.test import TestCase
from django.utils import timezone


class Mention(TestCase):
    def setUp(self):
        self.user = models.CustomUser.objects.create_user(
            username="jacob", email="jacob@…", password="top_secret"
        )

    def test_rules(self):
        r1 = models.Mention.objects.create(
            user=self.user,
            base_url="xojoc.pw",
            platforms=["r", "h", "l"],
            subreddits_only=["programming"],
            min_comments=4,
            min_score=3,
        )
        d1 = models.Discussion.objects.create(
            platform_id="r1",
            created_at=timezone.now(),
            scheme_of_story_url="https",
            schemeless_story_url="xojoc.pw",
            title="Alexandru Cojocaru",
            comment_count=10,
            score=20,
            tags=["programming"],
        )

        self.assertTrue(
            r1.mentionnotification_set.filter(discussion=d1).exists()
        )

        r2 = models.Mention.objects.create(
            user=self.user,
            base_url="twitter.com/xojoc",
        )

        d2 = models.Discussion.objects.create(
            platform_id="h2",
            created_at=timezone.now(),
            scheme_of_story_url="https",
            schemeless_story_url="twitter.com/xojoc/status/12345",
        )

        self.assertTrue(
            r2.mentionnotification_set.filter(discussion=d2).exists()
        )

        r3 = models.Mention.objects.create(user=self.user, keyword="discu.eu")

        d3 = models.Discussion.objects.create(
            platform_id="h3",
            created_at=timezone.now(),
            scheme_of_story_url="https",
            schemeless_story_url="discu.eu",
            title="Discussions around the web - discu.eu",
        )

        self.assertTrue(
            r3.mentionnotification_set.filter(discussion=d3).exists()
        )

        r4 = models.Mention.objects.create(
            user=self.user, keyword="two keywords"
        )

        d4 = models.Discussion.objects.create(
            platform_id="l4",
            created_at=timezone.now(),
            title="title with keywords, they are two.",
        )

        self.assertTrue(
            r4.mentionnotification_set.filter(discussion=d4).exists()
        )
