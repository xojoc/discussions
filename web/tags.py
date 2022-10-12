import re

import cleanurl

from web import title as web_title
from web import util


def __augment_tags(title, tags, keyword, atleast_tags=None, new_tag=None):
    if atleast_tags:
        if len(tags & atleast_tags) == 0:
            return

    if not new_tag and keyword:
        new_tag = keyword

    if not new_tag:
        return

    if new_tag in tags:
        return

    if keyword and keyword not in title:
        return

    tags.add(new_tag)


def __is_programming_related(title, url=None):
    return (
        set(title)
        & {
            "algorithm",
            "algorithms",
            "code",
            "function",
            "lambda",
            "library",
            "tutorial",
        }
    ) or (url and url.hostname and "github.com" in url.hostname)


def __programming_keyword(tags, title, url, keyword, new_tag=None):
    if not new_tag:
        new_tag = keyword
    if keyword in title and __is_programming_related(title, url):
        tags.add(new_tag)


def __is_nim_game(title, url=None):
    if util.is_sublist(title, ["nim", "game"]) or util.is_sublist(
        title, ["game", "of", "nim"]
    ):
        return True

    if url:
        pass

    return False


def __topic_nim(tags, title, url, platform):
    if platform in ("h", "u") and not __is_nim_game(title, url):
        __augment_tags(title, tags, "nim", None, "nimlang")
        __augment_tags(title, tags, "nim", None, "nimlang")

    __augment_tags(title, tags, "nimlang")

    if not __is_nim_game(title, url):
        __augment_tags(
            title, tags, "nim", {"programming", "gamedev"}, "nimlang"
        )

    if (
        url
        and "nim" in title
        and (
            "nim-lang.org" in url.hostname
            or (
                url.hostname == "github.com"
                and (url.path or "").startswith("/nim-lang")
            )
        )
    ):
        tags |= {"nimlang"}


def __topic_unix(tags, title, url, platform):
    __augment_tags(title, tags, "unix")
    __augment_tags(title, tags, "linux")
    __augment_tags(title, tags, "dragonflybsd")
    __augment_tags(title, tags, "freebsd")
    __augment_tags(title, tags, "netbsd")
    __augment_tags(title, tags, "openbsd")

    __augment_tags(
        title,
        tags,
        None,
        {
            "opensuse",
        },
        "linux",
    )

    __augment_tags(
        title,
        tags,
        None,
        {
            "dragonflybsd",
            "freebsd",
            "linux",
            "netbsd",
            "openbsd_gaming",
            "openbsd",
            "plan9",
        },
        "unix",
    )


def __topic_webdev(tags, title, url, platform):
    __augment_tags(title, tags, "node.js", None, "nodejs")
    __augment_tags(title, tags, "javascript")
    __augment_tags(None, tags, None, {"nodejs"}, "javascript")

    __augment_tags(
        title,
        tags,
        None,
        {"django", "flask", "javascript", "typescript", "rails"},
        "webdev",
    )


def __topic_zig(tags, title, url, platform):
    if platform in ("h", "u"):
        __augment_tags(title, tags, "zig", None, "ziglang")

    __augment_tags(title, tags, "ziglang")

    if "zag" not in title:
        __augment_tags(
            title, tags, "zig", {"programming", "gamedev"}, "ziglang"
        )

    if (
        url
        and "zig" in title
        and (
            "ziglang.org" in url.hostname
            or (
                url.hostname == "github.com"
                and (url.path or "").startswith("/ziglang")
            )
        )
    ):
        tags.add("ziglang")


def __topic_java(tags, title, url, platform):
    if platform == "u":
        __augment_tags(title, tags, "java")
    __augment_tags(title, tags, "java", {"programming", "gamedev", "webdev"})
    __augment_tags(title, tags, "openjdk", None, "java")

    try:
        ji = title.index("java")
        if title[ji + 1].isdigit() or (
            title[ji + 1] == "ee" and title[ji + 2].isdigit()
        ):
            tags.add("java")

    except Exception:
        pass

    if "java" in title and "spring" in title:
        tags.add("java")

    __programming_keyword(tags, title, url, "java")

    if (
        url
        and "java" in title
        and (
            "java.net" in url.hostname
            or "openjdk.org" in url.hostname
            or (
                url.hostname == "github.com"
                and (url.path or "").startswith("/openjdk")
            )
        )
    ):
        tags.add("java")


def __topic_php(tags, title, url, platform):
    __augment_tags(title, tags, None, {"laravel"}, "php")
    __augment_tags(title, tags, "php", {"programming", "gamedev", "webdev"})
    __programming_keyword(tags, title, url, "php")
    if platform == "h" and "php" in title:
        tags.add("php")
    if url and (url.hostname or "").startswith("php.net"):
        tags.add("php")


def __topic_rust(tags, title, url, platform):
    __augment_tags(title, tags, "rustlang")
    __augment_tags(
        title, tags, "rust", {"programming", "gamedev", "compsci"}, "rustlang"
    )

    __programming_keyword(tags, title, url, "rust", "rustlang")

    if "rust" in title and ("gcc" in title or "kernel" in title):
        tags.add("rust")

    __augment_tags(title, tags, "rustc", None, "rustlang")


def __topic_golang(tags, title, url, platform, original_title):
    __augment_tags(title, tags, "golang")

    if (
        ("programming" in tags or __is_programming_related(tags, url))
        and "Go" in original_title.split()
        and "game" not in title
    ):
        tags.add("golang")

    if (
        "go" in title
        and url
        and url.hostname
        and (
            "golang.org" in url.hostname
            or "go.dev" in url.hostname
            or (
                url.hostname == "github.com" and url.path.startswith("/golang")
            )
        )
    ):
        tags.add("golang")


def __lobsters(tags, title):
    tags -= {
        "ask",
        "audio",
        "book",
        "pdf",
        "show",
        "slides",
        "transcript",
        "video",
        "announce",
        "interview",
        "meta",
    }

    __augment_tags(
        title,
        tags,
        None,
        {
            "api",
            "debugging",
            "performance",
            "devops",
            "privacy",
            "practices",
            "practices",
            "scaling",
            "security",
            "testing",
            "virtualization",
        },
        "programming",
    )

    __augment_tags(
        title,
        tags,
        None,
        {
            "ai",
            "compilers",
            "distributed",
            "formalmethods",
            "graphics",
            "networking",
            "osdev",
            "plt",
            "cryptography",
        },
        "compsci",
    )


def __reddit(tags, title):
    __augment_tags(
        title,
        tags,
        None,
        {
            "baseball",
            "chess",
            "formula1",
            "hockey",
            "mma",
            "nba",
            "nfl",
            "soccer",
            "tennis",
            "wrestling",
        },
        "sport",
    )
    __augment_tags(title, tags, None, {"nfl"}, "football")
    __augment_tags(title, tags, None, {"nba"}, "basketball")
    __augment_tags(title, tags, None, {"apple"}, "technology")
    __augment_tags(title, tags, None, {"spacex"}, "space")

    __augment_tags(
        title,
        tags,
        None,
        {
            "compilers",
            "emudev",
            "cryptography",
            "machinelearning",
            "languagetechnology",
        },
        "compsci",
    )


def __hacker_news(tags, title):
    __augment_tags(title, tags, "docker")
    __augment_tags(title, tags, "lisp")
    __augment_tags(title, tags, "python")
    __augment_tags(title, tags, "typescript")


def __lambda_the_ultimate(tags, title):
    for t in tags:
        t = t.replace(" ", "-")
        t = t.replace("/", "-")
        tags.discard(t)
        tags.add(t)

    __augment_tags(title, tags, "haskell")
    __augment_tags(title, tags, "lisp")
    __augment_tags(title, tags, "python")
    __augment_tags(title, tags, "scheme")

    tags.difference_update(
        {
            "admin",
            "discussion",
            "general",
            "guest-bloggers",
            "here",
            "ltu-forum",
            "previously-on-ltu",
            "previously",
            "recent-discussion",
            "recently",
            "site-discussion",
        }
    )


def __laarc(tags, title):
    tags -= {"news", "meta", "laarc", "ask"}


def __from_title_url(tags, title, url):
    __augment_tags(
        title, tags, "python", {"programming", "webdev", "gamedev", "compsci"}
    )
    __augment_tags(title, tags, "cpp")
    __augment_tags(title, tags, "csharp")
    __augment_tags(title, tags, "haskell")
    __augment_tags(title, tags, "django", {"python", "webdev", "programming"})
    __augment_tags(title, tags, "flask", {"python", "webdev", "programming"})

    __augment_tags(title, tags, "rails", {"python", "webdev", "programming"})

    __augment_tags(title, tags, "perl", {"programming", "gamedev"})
    __augment_tags(title, tags, "webassembly")

    __augment_tags(title, tags, "spacex")
    __augment_tags(title, tags, "nintendo")
    __augment_tags(title, tags, "linkedin")

    if "metaprogramming" in title:
        tags |= {"programming"}

    if (
        url
        and "swift" in title
        and (url.hostname == "swift.org" or "swiftlang" in url.path)
    ):
        tags |= {"swiftlang"}

    if "quantum" in title and (
        "language" in title
        or "languages" in title
        or "computer" in title
        or "computers" in title
        or "computing" in title
        or "programming" in title
        or "algorithm" in title
    ):
        tags |= {"quantumcomputing", "programming"}

    __augment_tags(title, tags, "kotlin", {"programming", "gamedev"})

    __augment_tags(title, tags, "apl", {"programming"})
    if (
        url
        and "j" in title
        and (
            "jsoftware.com" in url.hostname
            or (
                url.hostname == "github.com"
                and (url.path or "").startswith("/jsoftware")
            )
        )
    ):
        tags |= {"apl"}

    if url and "apl" in title and ("github.com" in url.hostname):
        tags |= {"apl"}

    if "programming" in title and (
        "language" in title or "languages" in title
    ):
        tags |= {"programming"}

    if "programming" in tags and re.match(
        r".*(^v?|\sv?)(\d+\.?){2,4}[^ ]* release", " ".join(title)
    ):
        tags.add("release")


def __rename(tags, title, platform=None):
    to_replace = [
        (".net", "dotnet"),
        ("ai", "machinelearning", "l"),
        ("apljk", "apl", "r"),
        ("btc", "bitcoin", "r"),
        ("c_programming", "c", "r"),
        ("c#", "csharp"),
        ("c++", "cpp"),
        ("coding", "programming", "r"),
        ("crypto", "cryptography", "r"),
        ("d_language", "dlang", "r"),
        ("d", "dlang", "l"),
        ("economics", "economy", "r"),
        ("europes", "europe", "r"),
        ("go", "golang"),
        ("internationalpolitics", "politics", "r"),
        ("languagetechnology", "nlp", "r"),
        ("lc", "lambda-calculus", "u"),
        ("logic-declerative", "logic-declarative", "u"),
        ("machinelearningnews", "machinelearning", "r"),
        ("misc-books", "book", "u"),
        ("ml", "ocaml", "l"),
        ("moderatepolitics", "politics", "r"),
        ("nim", "nimlang", "r"),
        ("node", "nodejs", "r"),
        ("reddit.com", "reddit", "r"),
        ("rubylang", "ruby", "r"),
        ("rust_gamedev", ["gamedev", "rustlang"], "r"),
        ("rust", "rustlang"),
        ("software-eng", "programming", "u"),
        ("sports", "sport", "r"),
        ("squaredcircle", "wrestling", "r"),
        ("swift", "swiftlang"),
        ("teaching-&-learning", "teaching/learning", "u"),
        ("technews", ["technology", "news"], "r"),
        ("theory", ["plt", "compsci"], "u"),
        ("upliftingnews", "news", "r"),
        ("wasm", "webassembly", "l"),
        ("web_design", "webdesign", "r"),
        ("web", "webdev", "l"),
        ("worldevents", "news", "r"),
        ("worldnews", "news", "r"),
        ("zig", "ziglang", "l"),
        ("zig", "ziglang", "r"),
    ]
    for p in to_replace:
        if len(p) == 3 and p[2] != platform:
            continue
        if p[0] not in tags:
            continue
        tags -= {p[0]}
        if type(p[1]) is list:
            tags |= set(p[1])
        else:
            tags |= {p[1]}


def __enrich(tags, title):
    __augment_tags(
        title,
        tags,
        None,
        {
            "apl",
            "assembly",
            "c",
            "clojure",
            "cpp",
            "cprogramming",
            "csharp",
            "dlang",
            "dotnet",
            "elixir",
            "elm",
            "erlang",
            "forth",
            "fortran",
            "golang",
            "haskell",
            "java",
            "javascript",
            "kotlin",
            "lisp",
            "lua",
            "nimlang",
            "nodejs",
            "objectivec",
            "ocaml",
            "perl",
            "php",
            "python",
            "racket",
            "ruby",
            "rustlang",
            "scala",
            "scheme",
            "swiftlang",
            "typescript",
            "webassembly",
            "ziglang",
        },
        "programming",
    )

    __augment_tags(title, tags, None, {"django", "flask"}, "python")

    __augment_tags(title, tags, None, {"rails"}, "ruby")

    __augment_tags(title, tags, None, {"docker", "kubernetes"}, "devops")

    return tags


def __special_cases(tags, platform, title, url):
    if url and url.hostname == "joinmastodon.org":
        tags.discard("bitcoin")
        tags.discard("italy")


def normalize(tags, platform=None, title="", url=""):
    tags = tags or []
    tags = set(t.lower().strip() for t in tags)
    original_title = title or ""
    title = web_title.normalize(title, platform, url, tags, stem=False)
    title_tokens = title.split()

    url = (url or "").lower()
    curl = cleanurl.cleanurl(url)

    for _ in range(3):
        __topic_java(tags, title_tokens, curl, platform)
        __topic_nim(tags, title_tokens, curl, platform)
        __topic_php(tags, title_tokens, curl, platform)
        __topic_rust(tags, title_tokens, curl, platform)
        __topic_unix(tags, title_tokens, curl, platform)
        __topic_webdev(tags, title_tokens, curl, platform)
        __topic_zig(tags, title_tokens, curl, platform)
        __topic_golang(tags, title_tokens, curl, platform, original_title)

        __from_title_url(tags, title_tokens, curl)

        if platform == "l":
            __lobsters(tags, title_tokens)
        elif platform == "r":
            __reddit(tags, title_tokens)
        elif platform == "h":
            __hacker_news(tags, title_tokens)
        elif platform == "a":
            __laarc(tags, title_tokens)
        elif platform == "u":
            __lambda_the_ultimate(tags, title_tokens)

        __rename(tags, title_tokens, platform)
        __enrich(tags, title_tokens)

    __special_cases(tags, platform, title_tokens, curl)

    return sorted(list(tags))
