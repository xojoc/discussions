# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!

import unittest

from web import models
from web.category import Category


class UnitCategory(unittest.TestCase):
    def test_normalization(self):
        def d(platform, title, tags, url):
            s = models.Discussion(
                platform_id=f"{platform}123",
                scheme_of_story_url="https",
                schemeless_story_url=url,
                title=title,
                tags=tags,
            )
            s.pre_save()
            return s.category

        tests = [
            ("h", "discueu released", ["programming"], "discu.eu"),
            Category.RELEASE,
            (
                "r",
                "A minimalist video sharing application.",
                ["programming"],
                "sr.ht/~thecashewtrader/minv/",
            ),
            Category.PROJECT,
            ("l", "Games2d", ["programming"], "github.com/xojoc/games2d/"),
            Category.PROJECT,
            (
                "l",
                "Games2d",
                ["programming"],
                "github.com/xojoc/games2d/issues",
            ),
            Category.ARTICLE,
            ("h", "devops", ["devops"], "dev.tube/video/oX8af9kLhlk"),
            Category.VIDEO,
            ("h", "Is this a question?", [], ""),
            Category.ASK_PLATFORM,
            (
                "h",
                "Ask HN: Developers in rural locations: Do you feel you are missing out?",
                [],
                "",
            ),
            Category.ASK_PLATFORM,
            (
                "h",
                "Tell HN: important point",
                [],
                "",
            ),
            Category.TELL_PLATFORM,
        ]

        for u, r in zip(tests[0::2], tests[1::2], strict=True):
            rr = d(u[0], u[1], u[2], u[3])
            assert r == rr, u
