from web import models, forms
from django.test import TestCase
from django.utils import timezone


class Mention(TestCase):
    def setUp(self):
        self.user = models.CustomUser.objects.create_user(
            username="jacob", email="jacob@…", password="top_secret"
        )

    def __new_form(self, data):
        f1 = forms.MentionForm(data=data)
        r1 = None
        if f1.is_valid():
            r1 = f1.save(commit=False)
            r1.user = self.user
            r1.save()
        return f1, r1

    def test_rules(self):
        f1, r1 = self.__new_form(
            {
                "base_url": "https://m.xojoc.pw",
                "keywords": ["test1", "test2", "alexandru"],
                "exclude_platforms": ["u", "l"],
                "subreddits_exclude": ["/r/programming"],
                "min_comments": 4,
                "min_score": 3,
            }
        )
        self.assertFalse(f1.errors)
        self.assertEqual(r1.base_url, "m.xojoc.pw")
        self.assertEqual(r1.subreddits_exclude, ["programming"])

        d1 = models.Discussion.objects.create(
            platform_id="r1",
            created_at=timezone.now(),
            scheme_of_story_url="https",
            schemeless_story_url="www.xojoc.pw",
            title="Alexandru Cojocaru",
            comment_count=10,
            score=20,
            tags=["webdev"],
        )
        self.assertEqual(d1.canonical_story_url, "xojoc.pw")

        self.assertTrue(
            r1.mentionnotification_set.filter(discussion=d1).exists()
        )

        d1_1 = models.Discussion.objects.create(
            platform_id="r1_1",
            created_at=timezone.now(),
            scheme_of_story_url="https",
            schemeless_story_url="xojoc.pw",
            title="Alexandru Cojocaru",
            comment_count=10,
            score=20,
            tags=["programming"],
        )

        self.assertFalse(
            r1.mentionnotification_set.filter(discussion=d1_1).exists()
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

        f4, r4 = self.__new_form(
            {
                "keywords": [" two ", "   keywords"],
            }
        )
        self.assertFalse(f1.errors)

        d4 = models.Discussion.objects.create(
            platform_id="l4",
            created_at=timezone.now(),
            title="title with keywords, they are two.",
        )

        self.assertTrue(
            r4.mentionnotification_set.filter(discussion=d4).exists()
        )
