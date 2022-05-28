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
                n(None),
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
                n(
                    [],
                    None,
                    "Nim: Curated Packages",
                    url="https://github.com/nim-lang",
                ),
                n(
                    [],
                    None,
                    "Nim Version 1.6.6 Released",
                    url="https://nim-lang.org/blog/2022/05/05/version-166-released.html",
                ),
            ],
            [
                [],
                ["django", "programming", "python", "webdev"],
                ["web"],
                ["webdev"],
                ["linux", "unix"],
                ["nintendo"],
                ["linkedin"],
                ["nimlang", "programming"],
                ["nimlang", "programming"],
            ],
        )
