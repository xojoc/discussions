from web import tags
import unittest


class Tags(unittest.TestCase):
    def test_normalization(self):
        def n(ts, platform=None, title="", url=""):
            return tags.normalize(
                ts,
                platform,
                title,
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
                n([], title="The Nintendo Switch has now outsold the Wii"),
                n([], title="Why is LinkedIn so cringe?"),
            ],
            [
                ["django", "programming", "python", "webdev"],
                ["web"],
                ["webdev"],
                ["linux", "unix"],
                ["nintendo"],
                ["linkedin"],
            ],
        )
