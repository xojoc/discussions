from web import title as web_title
import cleanurl


def __augment_tags(title, tags, keyword, atleast_tags=None, new_tag=None):
    if atleast_tags:
        if len(tags & atleast_tags) == 0:
            return tags

    if not new_tag and keyword:
        new_tag = keyword.lower()

    if not new_tag:
        return tags

    if new_tag in tags:
        return tags

    if keyword:
        if keyword.lower() not in title.lower().split():
            return tags

    return tags | {new_tag}


def __replace_tag(tags, old_tag, new_tag):
    if old_tag not in tags:
        return tags

    return (tags - {old_tag}) | {new_tag}


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

    tags = __augment_tags(
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

    tags = __augment_tags(
        title,
        tags,
        None,
        {
            "ai",
            "distributed",
            "formalmethods",
            "graphics",
            "networking",
            "osdev",
            "plt",
        },
        "compsci",
    )

    return tags


def __reddit(tags, title):
    tags = __augment_tags(
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
    tags = __augment_tags(title, tags, None, {"nfl"}, "football")
    tags = __augment_tags(title, tags, None, {"nba"}, "basketball")
    tags = __augment_tags(title, tags, None, {"apple"}, "technology")
    tags = __augment_tags(title, tags, None, {"spacex"}, "space")
    tags = __augment_tags(title, tags, None, {"laravel"}, "php")

    tags = __augment_tags(
        title,
        tags,
        None,
        {"compilers", "emudev", "crypto"},
        "compsci",
    )
    return tags


def __hacker_news(tags, title):
    tags = __augment_tags(title, tags, "docker")
    tags = __augment_tags(title, tags, "javascript")
    tags = __augment_tags(title, tags, "lisp")
    tags = __augment_tags(title, tags, "nim", None, "nimlang")
    tags = __augment_tags(title, tags, "python")
    tags = __augment_tags(title, tags, "rust", None, "rustlang")
    tags = __augment_tags(title, tags, "typescript")
    tags = __augment_tags(title, tags, "zig", None, "ziglang")
    return tags


def __lambda_the_ultimate(tags, title):
    new_tags = set()
    for t in tags:
        t = t.replace(" ", "-")
        t = t.replace("/", "-")
        new_tags.add(t)

    new_tags = __augment_tags(title, new_tags, "haskell")
    new_tags = __augment_tags(title, new_tags, "java")
    new_tags = __augment_tags(title, new_tags, "lisp")
    new_tags = __augment_tags(title, new_tags, "nim", None, "nimlang")
    new_tags = __augment_tags(title, new_tags, "python")
    new_tags = __augment_tags(title, new_tags, "scheme")
    new_tags = __augment_tags(title, new_tags, "zig", None, "ziglang")

    return new_tags - {
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


def __laarc(tags, title):
    return tags - {"news", "meta", "laarc", "ask"}


def __from_title_url(tags, title, url):
    tags = __augment_tags(
        title, tags, "python", {"programming", "webdev", "gamedev", "compsci"}
    )
    tags = __augment_tags(title, tags, "golang")
    tags = __augment_tags(title, tags, "rustlang")
    tags = __augment_tags(
        title, tags, "rust", {"programming", "gamedev", "compsci"}, "rustlang"
    )
    tags = __augment_tags(title, tags, "cpp")
    tags = __augment_tags(title, tags, "csharp")
    tags = __augment_tags(title, tags, "haskell")
    tags = __augment_tags(
        title, tags, "django", {"python", "webdev", "programming"}
    )
    tags = __augment_tags(
        title, tags, "flask", {"python", "webdev", "programming"}
    )

    tags = __augment_tags(
        title, tags, "rails", {"python", "webdev", "programming"}
    )

    tags = __augment_tags(title, tags, "perl", {"programming", "gamedev"})
    tags = __augment_tags(title, tags, "webassembly")
    tags = __augment_tags(title, tags, "linux")
    tags = __augment_tags(title, tags, "dragonflybsd")
    tags = __augment_tags(title, tags, "freebsd")
    tags = __augment_tags(title, tags, "netbsd")
    tags = __augment_tags(title, tags, "openbsd")
    tags = __augment_tags(title, tags, "spacex")
    tags = __augment_tags(title, tags, "nintendo")
    tags = __augment_tags(title, tags, "linkedin")

    tokens = title.split()

    if "metaprogramming" in tokens:
        tags |= {"programming"}

    if (
        url
        and "swift" in tokens
        and (url.hostname == "swift.org" or "swiftlang" in url.path)
    ):
        tags |= {"swiftlang"}

    if "quantum" in tokens and (
        "language" in tokens
        or "languages" in tokens
        or "computer" in tokens
        or "computers" in tokens
        or "computing" in tokens
        or "programming" in tokens
        or "algorithm" in tokens
    ):
        tags |= {"quantumcomputing", "programming"}

    tags = __augment_tags(title, tags, "nimlang")
    tags = __augment_tags(
        title, tags, "nim", {"programming", "gamedev"}, "nimlang"
    )
    if (
        url
        and "nim" in tokens
        and (
            "nim-lang.org" in url.hostname
            or (
                url.hostname == "github.com"
                and (url.path or "").startswith("/nim-lang")
            )
        )
    ):
        tags |= {"nimlang"}

    tags = __augment_tags(title, tags, "ziglang")
    tags = __augment_tags(
        title, tags, "zig", {"programming", "gamedev"}, "ziglang"
    )
    if (
        url
        and "zig" in tokens
        and (
            "ziglang.org" in url.hostname
            or (
                url.hostname == "github.com"
                and (url.path or "").startswith("/ziglang")
            )
        )
    ):
        tags |= {"ziglang"}

    tags = __augment_tags(
        title, tags, "java", {"programming", "gamedev", "webdev"}
    )

    tags = __augment_tags(title, tags, "kotlin", {"programming", "gamedev"})

    tags = __augment_tags(
        title, tags, "php", {"programming", "gamedev", "webdev"}
    )

    tags = __augment_tags(title, tags, "apl", {"programming"})
    if (
        url
        and "j" in tokens
        and (
            "jsoftware.com" in url.hostname
            or (
                url.hostname == "github.com"
                and (url.path or "").startswith("/jsoftware")
            )
        )
    ):
        tags |= {"apl"}

    if url and "apl" in tokens and ("github.com" in url.hostname):
        tags |= {"apl"}

    if "programming" in tokens and (
        "language" in tokens or "languages" in tokens
    ):
        tags |= {"programming"}

    return tags


def __rename(tags, title, platform=None):
    to_replace = [
        (".net", "dotnet"),
        ("apljk", "apl", "r"),
        ("btc", "bitcoin", "r"),
        ("c_programming", "c", "r"),
        ("c#", "csharp"),
        ("c++", "cpp"),
        ("coding", "programming", "r"),
        ("d_language", "dlang", "r"),
        ("d", "dlang", "l"),
        ("europes", "europe", "r"),
        ("go", "golang"),
        ("internationalpolitics", "politics", "r"),
        ("lc", "lambda-calculus", "u"),
        ("logic-declerative", "logic-declarative", "u"),
        ("misc-books", "book", "u"),
        ("ml", "ocaml", "l"),
        ("moderatepolitics", "politics", "r"),
        ("nim", "nimlang", "r"),
        ("reddit.com", "reddit", "r"),
        ("rust_gamedev", ["gamedev", "rustlang"], "r"),
        ("rust", "rustlang"),
        ("rubylang", "ruby", "r"),
        ("software-eng", "programming", "u"),
        ("sports", "sport", "r"),
        ("squaredcircle", "wrestling", "r"),
        ("swift", "swiftlang"),
        ("teaching-&-learning", "teaching/learning", "u"),
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

    return tags


def __enrich(tags, title):
    tags = __augment_tags(
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

    tags = __augment_tags(title, tags, None, {"django", "flask"}, "python")
    tags = __augment_tags(
        title,
        tags,
        None,
        {"django", "flask", "javascript", "typescript", "rails"},
        "webdev",
    )

    tags = __augment_tags(title, tags, None, {"rails"}, "ruby")

    tags = __augment_tags(
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

    tags = __augment_tags(
        title, tags, None, {"docker", "kubernetes"}, "devops"
    )

    return tags


def normalize(tags, platform=None, title="", url=""):
    tags = tags or []
    tags = set(t.lower().strip() for t in tags)
    title = web_title.normalize(title, platform, url, tags, stem=False)
    url = (url or "").lower()
    curl = cleanurl.cleanurl(url)

    for _ in range(3):
        tags = __from_title_url(tags, title, curl)

        if platform == "l":
            tags = __lobsters(tags, title)
        elif platform == "r":
            tags = __reddit(tags, title)
        elif platform == "h":
            tags = __hacker_news(tags, title)
        elif platform == "a":
            tags = __laarc(tags, title)
        elif platform == "u":
            tags = __lambda_the_ultimate(tags, title)

        tags = __rename(tags, title, platform)
        tags = __enrich(tags, title)

    return sorted(list(tags))
