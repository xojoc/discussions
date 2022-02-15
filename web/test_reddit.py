from web import reddit
import unittest


class Reddit(unittest.TestCase):
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
        ]
        for h, u in zip(tests[0::2], tests[1::2]):
            hu = reddit._url_from_selftext(h)
            self.assertEqual(u, hu, msg=h)
