from web import tags, title as web_title
import unittest


class Tags(unittest.TestCase):
    def test_normalization(self):
        def n(ts, platform=None, title="", url=""):
            return tags.normalize(
                ts,
                platform,
                web_title.normalize(title, platform, url, ts, stem=True),
                url,
            )

        self.assertListEqual(
            [
                n(["django"]),
                n(["web"], platform="h"),
                n(["web"], platform="l"),
                n(
                    [],
                    platform="h",
                    title="Short guide to Linux phone desktops",
                    url="tuxphones.com/mobile-linux-phone-desktop-environments-de-comparison-interfaces/",
                ),
            ],
            [
                ["django", "programming", "python", "webdev"],
                ["web"],
                ["webdev"],
                ["linux", "unix"],
            ],
        )
