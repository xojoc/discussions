from web import category, models
import unittest


class Category(unittest.TestCase):
    def test_normalization(self):
        def d(platform, title, tags, url):
            s = models.Discussion(
                platform_id=f"{platform}123",
                scheme_of_story_url="https",
                schemeless_story_url=url,
                title=title,
                tags=tags,
            )
            s._pre_save()
            return category.derive(s)

        tests = [
            ("h", "discueu released", ["programming"], "discu.eu"),
            "release",
            (
                "r",
                "A minimalist video sharing application.",
                ["programming"],
                "sr.ht/~thecashewtrader/minv/",
            ),
            "project",
            ("l", "Games2d", ["programming"], "github.com/xojoc/games2d/"),
            "project",
            (
                "l",
                "Games2d",
                ["programming"],
                "github.com/xojoc/games2d/issues",
            ),
            "article",
            ("h", "devops", ["devops"], "dev.tube/video/oX8af9kLhlk"),
            "video",
            ("h", "Is this a question?", [], ""),
            "askplatform",
            (
                "h",
                "Ask HN: Developers in rural locations: Do you feel you are missing out?",
                [],
                "",
            ),
            "askplatform",
            (
                "h",
                "Tell HN: important point",
                [],
                "",
            ),
            "tellplatform",
        ]

        for u, r in zip(tests[0::2], tests[1::2]):
            rr = d(u[0], u[1], u[2], u[3])
            self.assertEqual(r, rr, msg=u)
