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
        ]
        for h, u in zip(tests[0::2], tests[1::2]):
            hu = reddit._url_from_selftext(h)
            self.assertEqual(u, hu, msg=h)
