# other parameters filled inside web/apps.py
topics = {
    "nim": {
        "name": "Nim",
        "short_description": "Nim programming language",
        "tags": {"nimlang"},
        "twitter": {
            "account": "NimDiscussions",
        },
        "mastodon": {
            "account": "@nim_discussions@mastodon.social",
        },
    },
    "zig": {
        "name": "Zig",
        "short_description": "Zig programming language",
        "tags": {"ziglang"},
        "twitter": {
            "account": "ZigDiscussions",
        },
        "mastodon": {
            "account": "@zig_discussions@mastodon.social",
        },
    },
    "java": {
        "name": "Java",
        "short_description": "Java programming language",
        "tags": {"java"},
        "twitter": {
            "account": "JavaDiscussions",
        },
        "mastodon": {
            "account": "@java_discussions@mastodon.social",
        },
    },
    "php": {
        "name": "PHP",
        "short_description": "PHP programming language",
        "tags": {"php"},
        "twitter": {
            "account": "PHPDiscussions",
        },
        "mastodon": {
            "account": "@php_discussions@mastodon.social",
        },
    },
    "apl": {
        "name": "APL",
        "short_description": "APL programming language",
        "tags": {"apl"},
        "twitter": {
            "account": "APLDiscussions",
        },
        "mastodon": {
            "account": "@apl_discussions@mastodon.social",
        },
    },
    "rust": {
        "name": "Rust",
        "short_description": "Rust programming language",
        "tags": {"rustlang"},
        "twitter": {
            "account": "RustDiscussions",
        },
        "mastodon": {
            "account": "@rust_discussions@mastodon.social",
        },
    },
    "golang": {
        "name": "Golang",
        "short_description": "Go programming language",
        "tags": {"golang"},
        "twitter": {
            "account": "GoDiscussions",
        },
        "mastodon": {
            "account": "@golang_discussions@mastodon.social",
        },
    },
    "python": {
        "name": "Python",
        "short_description": "Python programming language",
        "tags": {"python"},
        "twitter": {
            "account": "IntPyDiscu",
        },
        "mastodon": {
            "account": "@python_discussions@mastodon.social",
        },
    },
    "candcpp": {
        "name": "C & C++",
        "short_description": "C & C++ programming languages",
        "tags": {"c", "cpp"},
        "twitter": {
            "account": "CPPDiscussions",
        },
        "mastodon": {
            "account": "@c_discussions@mastodon.social",
        },
    },
    "haskell": {
        "name": "Haskell",
        "short_description": "Haskell programming language",
        "tags": {"haskell"},
        "twitter": {
            "account": "HaskellDiscu",
        },
        "mastodon": {
            "account": "@haskell_discussions@mastodon.social",
        },
    },
    "lisp": {
        "name": "Lisp & Scheme",
        "short_description": "Lisp & Scheme",
        "tags": {"lisp", "scheme", "racket"},
        "twitter": {
            "account": "LispDiscussions",
        },
        "mastodon": {
            "account": "@lisp_discussions@mastodon.social",
        },
    },
    "erlang": {
        "name": "Erlang & Elixir",
        "short_description": "Erlang & Elixir",
        "tags": {"erlang", "elixir"},
        "twitter": {
            "account": "ErlangDiscu",
        },
        "mastodon": {
            "account": "@erlang_discussions@mastodon.social",
        },
    },
    "ruby": {
        "name": "Ruby",
        "short_description": "Ruby programming language",
        "tags": {"ruby"},
        "twitter": {
            "account": "RubyDiscussions",
        },
        "mastodon": {
            "account": "@ruby_discussions@mastodon.social",
        },
    },
    "unix": {
        "name": "Unix",
        "short_description": "Unix and Unix-like operating systems",
        "tags": {"unix"},
        "twitter": {
            "account": "UnixDiscussions",
        },
        "mastodon": {
            "account": "@unix_discussions@mastodon.social",
        },
    },
    "compsci": {
        "name": "Computer science",
        "short_description": "Computer science",
        "tags": {"compsci"},
        "twitter": {
            "account": "CompsciDiscu",
        },
        "mastodon": {
            "account": "@compsci_discussions@mastodon.social",
        },
    },
    "devops": {
        "name": "DevOps",
        "short_description": "DevOps",
        "tags": {"devops", "docker", "kubernetes"},
        "twitter": {
            "account": "DevopsDiscu",
        },
        "mastodon": {
            "account": "@devops_discussions@mastodon.social",
        },
    },
    "programming": {
        "name": "Software Development",
        "short_description": "Software Development",
        "tags": {"programming"},
        "twitter": {
            "account": "ProgDiscussions",
        },
        "mastodon": {
            "account": "@programming_discussions@mastodon.social",
        },
    },
    "hackernews": {
        "name": "Hacker News",
        "short_description": "Hacker News",
        "tags": set(),
        "platform": "h",
        "twitter": {
            "account": "HNDiscussions",
        },
        "mastodon": {
            "account": "@hn_discussions@mastodon.social",
        },
    },
    "laarc": {
        "name": "Laarc",
        "short_description": "Laarc",
        "tags": set(),
        "platform": "a",
        "twitter": {
            "account": "LaarcDiscu",
        },
        "mastodon": {
            "account": "@laarc_discussions@mastodon.social",
        },
    },
}

topics_choices = sorted([(key, item["name"]) for key, item in topics.items()])


def get_account_configuration(platform, username):
    for topic_key, topic in topics.items():
        if not topic.get("twitter"):
            continue
        if not topic.get(platform):
            continue
        if not topic.get(platform).get("account"):
            continue

        topic_account = topic.get("twitter").get("account")
        if not topic_account:
            continue

        if topic_account.lower() == username.lower():
            return topic.get(platform)
