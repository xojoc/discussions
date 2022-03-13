from web import title as web_title


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
            "soccer",
            "nfl",
            "chess",
            "nba",
            "hockey",
            "formula1",
            "baseball",
            "wrestling",
            "mma",
        },
        "sport",
    )
    tags = __augment_tags(title, tags, None, {"nfl"}, "football")
    tags = __augment_tags(title, tags, None, {"nba"}, "basketball")
    tags = __augment_tags(title, tags, None, {"apple"}, "technology")
    tags = __augment_tags(title, tags, None, {"spacex"}, "space")
    tags = __augment_tags(title, tags, None, {"laravel"}, "php")
    return tags


def __hacker_news(tags, title):
    tags = __augment_tags(title, tags, "python")
    tags = __augment_tags(title, tags, "docker")
    tags = __augment_tags(title, tags, "javascript")
    tags = __augment_tags(title, tags, "typescript")
    tags = __augment_tags(title, tags, "lisp")
    tags = __augment_tags(title, tags, "rust", None, "rustlang")
    return tags


def __lambda_the_ultimate(tags, title):
    new_tags = set()
    for t in tags:
        t = t.replace(" ", "-")
        t = t.replace("/", "-")
        new_tags.add(t)

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
    tags = __augment_tags(title, tags, "golang")
    tags = __augment_tags(title, tags, "rustlang")
    tags = __augment_tags(title, tags, "rust", {"programming"}, "rustlang")
    tags = __augment_tags(title, tags, "cpp")
    tags = __augment_tags(title, tags, "csharp")
    tags = __augment_tags(title, tags, "haskell")
    tags = __augment_tags(title, tags, "java", {"programming"})
    tags = __augment_tags(
        title, tags, "django", {"python", "webdev", "programming"}
    )
    tags = __augment_tags(
        title, tags, "flask", {"python", "webdev", "programming"}
    )
    tags = __augment_tags(title, tags, "perl", {"programming"})
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

    if "swift" in tokens and ("swift.org" in url or "swiftlang" in url):
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

    return tags


def __rename(tags, title, platform=None):
    to_replace = [
        (".net", "dotnet"),
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
        ("ml", "ocaml", "l"),
        ("moderatepolitics", "politics", "r"),
        ("nim", "nimlang", "r"),
        ("reddit.com", "reddit", "r"),
        ("rust", "rustlang"),
        ("sports", "sport", "r"),
        ("squaredcircle", "wrestling", "r"),
        ("swift", "swiftlang"),
        ("upliftingnews", "news", "r"),
        ("web_design", "webdesign", "r"),
        ("web", "webdev", "l"),
        ("wasm", "webassembly", "l"),
        ("worldevents", "news", "r"),
        ("worldnews", "news", "r"),
        ("lc", "lambda-calculus", "u"),
        ("logic-declerative", "logic-declarative", "u"),
        ("misc-books", "book", "u"),
        ("software-eng", "software-engineering", "u"),
        ("teaching-&-learning", "teaching/learning", "u"),
    ]
    for p in to_replace:
        if len(p) == 3 and p[2] != platform:
            continue
        tags = __replace_tag(tags, p[0], p[1])

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
            "dlang",
            "dotnet",
            "elixir",
            "elm",
            "erlang",
            "fortran",
            "golang",
            "haskell",
            "java",
            "javascript",
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
            "zig",
        },
        "programming",
    )

    tags = __augment_tags(title, tags, None, {"django", "flask"}, "python")
    tags = __augment_tags(
        title,
        tags,
        None,
        {"django", "flask", "javascript", "typescript"},
        "webdev",
    )

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
    url = url.lower()

    for _ in range(3):
        tags = __from_title_url(tags, title, url)

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
