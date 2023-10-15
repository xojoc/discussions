# Copyright 2023 Alexandru Cojocaru AGPLv3 or later - no warranty!


from operator import attrgetter

from django.db import models


class Platform(models.TextChoices):
    HACKER_NEWS = "h", "Hacker News"
    LAMBDA_THE_ULTIMATE = "u", "Lambda the Ultimate"
    REDDIT = "r", "Reddit"
    LOBSTERS = "l", "Lobsters"
    BARNACLES = "b", "Barnacles"
    GAMBERO = "g", "Gambero"
    TILDE_NEWS = "t", "Tilde news"
    STANDARD = "s", "Standard"
    ECHO_JS = "e", "Echo JS"
    LAARC = "a", "Laarc"

    @property
    def url(self) -> str:
        urls = {
            self.HACKER_NEWS: "https://news.ycombinator.com",
            self.LAMBDA_THE_ULTIMATE: "http://lambda-the-ultimate.org",
            self.REDDIT: "https://www.reddit.com",
            self.LOBSTERS: "https://lobste.rs",
            self.BARNACLES: "https://barnacl.es",
            self.GAMBERO: "https://gambe.ro",
            self.TILDE_NEWS: "https://tilde.news",
            self.STANDARD: "https://std.bz",
            self.ECHO_JS: "https://echojs.com",
            self.LAARC: "https://www.laarc.io",
        }

        return urls[self]

    @property
    def tag_url(self) -> str:
        suffix = ""
        match self:
            case self.REDDIT:
                suffix = "/r"
            case self.LOBSTERS | self.BARNACLES | self.GAMBERO | self.TILDE_NEWS | self.STANDARD:
                suffix = "/t"
            case self.LAARC:
                suffix = "/l"
            case self.HACKER_NEWS | self.ECHO_JS:
                # Platform doesn't have tags
                suffix = ""
            case self.LAMBDA_THE_ULTIMATE:
                # LtU has taxonomy
                suffix = ""

        return self.url + suffix

    @property
    def order(self) -> int:
        order = {
            self.HACKER_NEWS: 10,
            self.LAMBDA_THE_ULTIMATE: 15,
            self.REDDIT: 20,
            self.LOBSTERS: 30,
            self.BARNACLES: 40,
            self.GAMBERO: 50,
            self.TILDE_NEWS: 60,
            self.STANDARD: 70,
            self.ECHO_JS: 80,
            self.LAARC: 90,
        }

        return order.get(self, 100)

    @classmethod
    def dict_label_url(cls) -> dict[str, tuple[str, str]]:
        ps = {}
        for p in sorted(cls, key=attrgetter("order")):
            ps[p.value] = (p.label, p.url)
        return ps

    @property
    def score_label(self) -> str:
        if self.value == self.LAMBDA_THE_ULTIMATE:
            return "reads"
        return "points"

    def thread_url(self, key: str, subreddit: str | None = None) -> str:
        bu = self.url
        match self:
            case self.REDDIT:
                return f"{bu}/r/{subreddit}/comments/{key}"
            case self.HACKER_NEWS | self.LAARC:
                return f"{bu}/item?id={key}"
            case self.LAMBDA_THE_ULTIMATE:
                return f"{bu}/{key}"
            case self.LOBSTERS | self.BARNACLES | self.GAMBERO | self.TILDE_NEWS | self.STANDARD:
                return f"{bu}/s/{key}"
            case self.ECHO_JS:
                return f"{bu}/news/{key}"
        return ""
