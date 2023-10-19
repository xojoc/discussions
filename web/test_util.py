# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import unittest

from web import util


class UnitTitle(unittest.TestCase):
    def test_url_root(self):
        tests = [
            "https://xojoc.pw/games2d/4snakes",
            "xojoc.pw",
            "https://github.com/xojoc/games2d",
            "github.com/xojoc",
            "https://gitlab.com/xojoc/engine",
            "gitlab.com/xojoc",
            "https://twitter.com/IndieRandWeb/status/1523963747324289024",
            "twitter.com/IndieRandWeb",
            "https://mastodon.social/web/@php_discussions/109117309015003104",
            "mastodon.social/web/@php_discussions",
        ]

        for u, r in zip(tests[0::2], tests[1::2], strict=True):
            rr = util.url_root(u)
            assert r == rr, u
