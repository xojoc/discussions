# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import unittest

from web import reddit


class UnitReddit(unittest.TestCase):
    def test_selftext_url(self):
        tests = [
            "[IPv4](http://0.0.0.0:33769)",
            None,
            "[GNU](https://gnu.org)",
            "https://gnu.org",
            "[Blacklisted](https://imgur.com/path)",
            None,
            "[Blacklisted](https://reddit.com/path) [Second URL](https://mastodon.social)",
            "https://mastodon.social",
            "[IPv6](http://[2001:db8::1]:80)",
            None,
            "[Localhost](http://localhost:3000)",
            None,
            "[Views.py](https://views.py)",
            None,
            "[build.rs](https://build.rs)",
            None,
            "Do anyone know from where can i learn [ASP.NET](https://ASP.NET/)? (i already know c#)",
            None,
            "like the [readme.md](https://readme.md) to be self-explanatory",
            None,
            "[Single link](https://discu.eu/)",
            "https://discu.eu/",
            "[more than](https://discu.eu) two [links](https://xojoc.pw/)",
            None,
            "'task_id'\n\n[**urls. py**](https://urls.py)**:**\n\n",
            None,
            "`&MyStruct { data: &`[`self.data`](https://self.data)`[3..8] }`",
            None,
        ]
        for h, u in zip(tests[0::2], tests[1::2], strict=True):
            hu = reddit._url_from_selftext(h)
            assert u == hu, h

        assert None is reddit._url_from_selftext(
            "[Single link](https://discu.eu/)",
            "Help me with discu.eu",
        )
        assert None is reddit._url_from_selftext(
            "[Yes](https://xojoc.pw/)",
            "Is this X?",
        )

    def test_url(self):
        tests = [
            "www.reddit.com/gallery/xykno0",
            True,
            "preview.redd.it/aaa.png",
            True,
            "i.imgur.com/aaa.jpg",
            True,
            "xojoc.pw",
            False,
        ]
        for h, u in zip(tests[0::2], tests[1::2], strict=True):
            hu = reddit._url_blacklisted(h)
            assert u == hu, h
