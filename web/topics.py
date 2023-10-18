# Copyright 2022 Alexandru Cojocaru AGPLv3 or later - no warranty!
import typing
from typing import TypedDict

from celery import shared_task


class _SocialProfileRequired(TypedDict):
    """Required fields for Social profile/account."""

    account: str
    token: str
    token_secret: str


class SocialProfile(_SocialProfileRequired, total=False):
    """Fields for Social profile/account."""


class Twitter(SocialProfile):
    """Twitter account data."""


class Mastodon(SocialProfile):
    """Mastodon account data."""


class _TopicDataRequired(TypedDict):
    topic_key: str
    name: str
    short_description: str
    tags: set[str]
    twitter: Twitter
    mastodon: Mastodon
    # filled inside apps.py
    from_email: str
    # filled inside apps.py
    email: str


class TopicData(_TopicDataRequired, total=False):
    """Topic of a given story/discussion."""

    platform: str
    home_link: str
    noun: str | None
    mailto_subscribe: str | None
    mailto_unsubscribe: str | None


topics: dict[str, TopicData] = {
    "nim": {
        "topic_key": "nim",
        "name": "Nim",
        "short_description": "Nim programming language",
        "tags": {"nimlang"},
        "twitter": {
            "account": "NimDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@nim_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://nim-lang.org/",
        "from_email": "",
        "email": "",
    },
    "zig": {
        "topic_key": "zig",
        "name": "Zig",
        "short_description": "Zig programming language",
        "tags": {"ziglang"},
        "twitter": {
            "account": "ZigDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@zig_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://ziglang.org/",
        "noun": "Zig programmer",
        "from_email": "",
        "email": "",
    },
    "java": {
        "topic_key": "java",
        "name": "Java",
        "short_description": "Java programming language",
        "tags": {"java", "jvm", "kotlin"},
        "twitter": {
            "account": "JavaDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@java_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://www.java.com/en/",
        "from_email": "",
        "email": "",
    },
    "php": {
        "topic_key": "php",
        "name": "PHP",
        "short_description": "PHP programming language",
        "tags": {"php"},
        "twitter": {
            "account": "PHPDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@php_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://www.php.net/",
        "from_email": "",
        "email": "",
    },
    "apl": {
        "topic_key": "apl",
        "name": "APL",
        "short_description": "Array Programming Languages",
        "tags": {"apl"},
        "twitter": {
            "account": "APLDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@apl_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://aplwiki.com/",
        "from_email": "",
        "email": "",
    },
    "rust": {
        "topic_key": "rust",
        "name": "Rust",
        "short_description": "Rust programming language",
        "tags": {"rustlang"},
        "twitter": {
            "account": "RustDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@rust_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://www.rust-lang.org/",
        "noun": "Rustacean",
        "from_email": "",
        "email": "",
    },
    "golang": {
        "topic_key": "golang",
        "name": "Golang",
        "short_description": "Go programming language",
        "tags": {"golang"},
        "twitter": {
            "account": "GoDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@golang_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://go.dev/",
        "noun": "Gopher",
        "from_email": "",
        "email": "",
    },
    "python": {
        "topic_key": "python",
        "name": "Python",
        "short_description": "Python programming language",
        "tags": {"python"},
        "twitter": {
            "account": "IntPyDiscu",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@python_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://www.python.org/",
        "noun": "Pythonista",
        "from_email": "",
        "email": "",
    },
    "candcpp": {
        "topic_key": "candcpp",
        "name": "C & C++",
        "short_description": "C & C++ programming languages",
        "tags": {"c", "cpp"},
        "twitter": {
            "account": "CPPDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@c_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "from_email": "",
        "email": "",
    },
    "haskell": {
        "topic_key": "haskell",
        "name": "Haskell",
        "short_description": "Haskell programming language",
        "tags": {"haskell"},
        "twitter": {
            "account": "HaskellDiscu",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@haskell_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://www.haskell.org/",
        "noun": "Haskeller",
        "from_email": "",
        "email": "",
    },
    "lisp": {
        "topic_key": "lisp",
        "name": "Lisp & Scheme",
        "short_description": "Lisp & Scheme",
        "tags": {"lisp", "scheme", "racket", "clojure"},
        "twitter": {
            "account": "LispDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@lisp_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "from_email": "",
        "email": "",
    },
    "erlang": {
        "topic_key": "erlang",
        "name": "Erlang & Elixir",
        "short_description": "Erlang & Elixir",
        "tags": {"erlang", "elixir"},
        "twitter": {
            "account": "ErlangDiscu",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@erlang_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://www.erlang.org/",
        "from_email": "",
        "email": "",
    },
    "ruby": {
        "topic_key": "ruby",
        "name": "Ruby",
        "short_description": "Ruby programming language",
        "tags": {"ruby"},
        "twitter": {
            "account": "RubyDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@ruby_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "home_link": "https://www.ruby-lang.org/en/",
        "noun": "Rubyist",
        "from_email": "",
        "email": "",
    },
    "unix": {
        "topic_key": "unix",
        "name": "Unix",
        "short_description": "Unix and Unix-like operating systems",
        "tags": {"unix"},
        "twitter": {
            "account": "UnixDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@unix_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "from_email": "",
        "email": "",
    },
    "compsci": {
        "topic_key": "compsci",
        "name": "Computer science",
        "short_description": "Computer science",
        "tags": {"compsci"},
        "twitter": {
            "account": "CompsciDiscu",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@compsci_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "from_email": "",
        "email": "",
    },
    "devops": {
        "topic_key": "devops",
        "name": "DevOps",
        "short_description": "DevOps",
        "tags": {"devops", "docker", "kubernetes"},
        "twitter": {
            "account": "DevopsDiscu",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@devops_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "from_email": "",
        "email": "",
    },
    "webdev": {
        "topic_key": "webdev",
        "name": "Web Development",
        "short_description": "Web Development",
        "tags": {
            "webdev",
            "webassembly",
            "javascript",
            "typescript",
            "css",
            "nodejs",
        },
        "twitter": {
            "account": "WebdevDiscu",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@webdev_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "noun": "Web Developer",
        "from_email": "",
        "email": "",
    },
    "programming": {
        "topic_key": "programming",
        "name": "Software Development",
        "short_description": "Software Development",
        "tags": {"programming"},
        "twitter": {
            "account": "ProgDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@programming_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "noun": "Programmer",
        "from_email": "",
        "email": "",
    },
    "hackernews": {
        "topic_key": "hackernews",
        "name": "Hacker News",
        "short_description": "Hacker News",
        "tags": set(),
        "platform": "h",
        "twitter": {
            "account": "HNDiscussions",
            "token": "",
            "token_secret": "",
        },
        "mastodon": {
            "account": "@hn_discussions@mastodon.social",
            "token": "",
            "token_secret": "",
        },
        "from_email": "",
        "email": "",
    },
    # "laarc": {
    #     "name": "Laarc",
    #     "short_description": "Laarc",
    #     "tags": set(),
    #     "platform": "a",
    #     "twitter": {
    #         "account": "LaarcDiscu",
    #     },
    #     "mastodon": {
    #         "account": "@laarc_discussions@mastodon.social",
    #     },
    # },
}

topics_choices = sorted([(key, item["name"]) for key, item in topics.items()])


def get_account_configuration(
    platform_key: str,
    username: str,
) -> Twitter | Mastodon | None:
    """Get account configuration for the given social platform.

    Args:
        platform_key: social media platform (Twitter, Mastodon, etc.)
        username: bot's username for the corresponding topic

    Returns: account configuration of the bot for the given social platform.
    """
    for topic in topics.values():
        platform = topic.get(platform_key)
        if not platform:
            continue
        platform = typing.cast(SocialProfile, platform)
        account = platform.get("account")
        if not account:
            continue

        if account.lower() == username.lower():
            return platform

        twitter_account = topic.get("twitter").get("account")
        if twitter_account and twitter_account.lower() == username.lower():
            return platform
    return None


def get_topic_by_email(email: str) -> tuple[str, TopicData] | None:
    """Get the topic which corresponds to a sender email.
       .e.g. weekly_rust@discu.eu -> Rust.

    Args:
        email (): email to match to the topic

    Returns: the corresponding topic
    """
    for topic_key, topic in topics.items():
        if topic.get("email") == email:
            return topic_key, topic

    return None


@shared_task
def task_update_followers_count():
    counts = {}
    for topic in topics:
        pass
