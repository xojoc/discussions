from web import tags
import unittest


class UnitTags(unittest.TestCase):
    def test_normalization(self):
        def n(ts, platform=None, title="", url=""):
            return tags.normalize(
                ts,
                platform,
                title,
                url,
            )

        normalization = [
            n(["django"]),
            ["django", "programming", "python", "webdev"],
            n(["web"], platform="h"),
            ["web"],
            n(["web"], platform="l"),
            ["webdev"],
            n(
                [],
                platform="h",
                title="Short guide to Linux phone desktops",
                url="tuxphones.com/mobile-linux-phone-desktop-environments-de-comparison-interfaces/",
            ),
            ["linux", "unix"],
            n([], title="The Nintendo Switch has now outsold the Wii"),
            ["nintendo"],
            n([], title="Why is LinkedIn so cringe?"),
            ["linkedin"],
            n(
                [],
                None,
                "Zig Programming Language",
                url="https://ziglang.org/",
            ),
            ["programming", "ziglang"],
            n(
                [],
                None,
                "Zig self hosted compiler is now capable of building itself",
                url="https://github.com/ziglang/zig/pull/11442",
            ),
            ["programming", "ziglang"],
            n(
                [],
                None,
                "Zig 0.9.1 Released",
                url="https://ziglang.org/download/0.9.1/release-notes.html",
            ),
            ["programming", "ziglang"],
            n(["rust_gamedev"], platform="r"),
            ["gamedev", "programming", "rustlang"],
            n(
                [],
                None,
                "Nim: Curated Packages",
                url="https://github.com/nim-lang",
            ),
            {"nimlang", "programming"},
            n(
                [],
                None,
                "Nim Version 1.6.6 Released",
                url="https://nim-lang.org/blog/2022/05/05/version-166-released.html",
            ),
            {"nimlang", "programming", "release"},
            n(
                [],
                None,
                "OpenBSD article",
            ),
            {"unix", "openbsd"},
            n(
                ["programming"],
                None,
                'Author of "Unix in Rust" abandons Rust in favour of Nim',
                "https://github.com/ckkashyap/rustix/issues/8",
            ),
            {"nimlang", "rustlang", "programming"},
            n(["programming"], None, "project xyz v0.1.3alpha released"),
            ["release"],
            n(
                [],
                "h",
                "Highly performant Node.js native extensions in Nim",
                "https://github.com/andi23rosca/napi-nim#write-nodejs-native-extensions-in-nim",
            ),
            {"nodejs"},
            n(
                [],
                "h",
                "Project Kulla: OpenJDK REPL",
                "https://mail.openjdk.java.net/pipermail/announce/2014-August/000181.html",
            ),
            {"java"},
            n(
                [],
                "h",
                "Java EE 8 Delayed until End of 2017, Oracle Announces at JavaOne",
                "https://www.infoq.com/news/2016/09/java-ee-delayed-2017",
            ),
            {"java"},
            n(
                [],
                "h",
                "Comparing Java Lambda Expressions to Scala Functions",
                "https://blog.madhukaraphatak.com/latest-java-2",
            ),
            {"java"},
            n(
                [],
                "h",
                "Incremental Parsing in Go",
                "https://dev-nonsense.com/posts/incremental-parsing-in-go/",
            ),
            {"golang"},
            n(
                ["programming"],
                "l",
                "RISC In 2022",
                "https://wiki.alopex.li/RiscIn2022",
            ),
            {"compsci"},
            n(
                ["programming"],
                "r",
                "CORS: An Introduction",
                "https://simplelocalize.io/blog/posts/what-is-cors/",
            ),
            {"webdev"},
            n(
                [],
                "h",
                "Heroku Free Alternatives",
                "https://github.com/Engagespot/heroku-free-alternatives",
            ),
            {"devops"},
            n(
                [],
                "h",
                "Tailwind CSS v3.2: revisiting my “feature creep” warning",
                "https://www.brycewray.com/posts/2022/10/tailwind-css-v3-2-revisiting-feature-creep-warning/",
            ),
            {"webdev"},
            n(
                [],
                "h",
                "5 Years of Pop_OS",
                "https://blog.system76.com/post/celebrating-5-years-of-pop_os/",
            ),
            {"linux"},
            n(
                [],
                "h",
                "AI models that predict disease are not as accurate as reports might suggest",
                "https://www.scientificamerican.com/article/ai-in-medicine-is-overhyped/",
            ),
            {"machinelearning", "compsci"},
        ]

        for nts, ets in zip(normalization[0::2], normalization[1::2]):
            nts = set(nts)
            ets = set(ets)
            self.assertTrue(
                nts.issuperset(ets),
                msg=f"got {nts} expected {ets} diff {ets-nts}",
            )

        missing = [
            n(
                ["programming", "python"],
                None,
                "Minimax in Python: Learn How to Lose the Game of Nim – Real Python",
                "https://realpython.com/python-minimax-nim/",
            ),
            {"nimlang"},
            n(
                ["admin"],
                "u",
                "LtU announcment",
            ),
            {"admin"},
            n(
                ["news"],
                "a",
                "Laarc post",
            ),
            {"news"},
            n(
                ["meta"],
                "l",
                "Lobsters meta post",
            ),
            {"meta"},
        ]

        for nts, mts in zip(missing[0::2], missing[1::2]):
            self.assertFalse(set(nts) & mts, msg=nts)
