# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
from typing import Self

import urllib3
from django.db.models import IntegerChoices

from web.platform import Platform
from web.tags import normalize as normalize_tags
from web.title import normalize as normalize_title

logger = logging.getLogger(__name__)


class Category(IntegerChoices):
    ARTICLE = 0, "Article"
    ASK_PLATFORM = 1, "Ask"
    TELL_PLATFORM = 2, "Tell"
    RELEASE = 3, "Release"
    PROJECT = 4, "Project"
    VIDEO = 5, "Video"

    @property
    def plural(self) -> str:
        match self:
            case self.ARTICLE:
                return "Articles"
            case self.ASK_PLATFORM | self.TELL_PLATFORM:
                return self.label
            case self.RELEASE:
                return "Releases"
            case self.PROJECT:
                return "Projects"
            case self.VIDEO:
                return "Videos"

    @property
    def order(self) -> int:
        match self:
            case self.ARTICLE:
                return 10
            case self.ASK_PLATFORM:
                return 20
            case self.TELL_PLATFORM:
                return 30
            case self.RELEASE:
                return 40
            case self.PROJECT:
                return 50
            case self.VIDEO:
                return 60

    def name_platform(self, platform: Platform) -> str:
        if platform == Platform.HACKER_NEWS:
            if self in {Category.TELL_PLATFORM, Category.ASK_PLATFORM}:
                return f"{self.label} HN"

        return self.plural

    @classmethod
    def derive(
        cls,
        title: str,
        url: str,
        story_tags: list[str],
        platform: Platform,
    ) -> Self:
        u = None
        try:
            u = urllib3.util.parse_url(url)
        except ValueError:
            logger.warning("category: url parsing failed")

        path, host = "", ""
        if u:
            path = (u.path or "").strip()
            host = (u.host or "").strip()

        path_components = [p for p in path.split("/") if p]

        title = title or ""
        tags = set(normalize_tags(story_tags, platform, title, url))
        title_tokens = normalize_title(title, platform, url, tags).split()

        for f in derive_functions:
            cat = f(platform, title_tokens, host, path_components, tags)
            if cat:
                return cat

        if (
            platform == Platform.HACKER_NEWS
            and not url
            and title.endswith("?")
        ):
            return Category.ASK_PLATFORM

        return Category.ARTICLE


def __derive_release(
    platform: Platform,
    title_tokens: list[str],
    host: str,
    path_components: list[str],
    tags: set[str],
) -> Category | None:
    _ = platform
    _ = host
    _ = path_components
    if "programming" in tags and (
        "release" in title_tokens or "released" in title_tokens
    ):
        return Category.RELEASE
    if "release" in tags:
        return Category.RELEASE
    return None


def __derive_project(
    platform: Platform,
    title_tokens: list[str],
    host: str,
    path_components: list[str],
    tags: set[str],
) -> Category | None:
    _ = platform
    _ = title_tokens
    _ = tags
    if (
        host
        in {
            "github.com",
            "gitlab.com",
            "bitbucket.org",
            "gitea.com",
        }
        and len(path_components) == 2
    ):
        return Category.PROJECT

    if (
        host in ("sr.ht")
        and len(path_components) == 2
        and path_components[0][0] == "~"
    ):
        return Category.PROJECT

    if host in {"savannah.gnu.org", "savannah.nongnu.org"} and (
        len(path_components) > 1 and path_components[0] == "projects"
    ):
        return Category.PROJECT

    if host in ("crates.io") and (
        len(path_components) > 1 and path_components[0] == "/crates/"
    ):
        return Category.PROJECT

    if host in ("docs.rs") and len(path_components) == 1:
        return Category.PROJECT

    return None


def __derive_video(
    platform: Platform,
    title_tokens: list[str],
    host: str,
    path_components: list[str],
    tags: set[str],
) -> Category | None:
    _ = platform
    _ = title_tokens
    _ = path_components
    _ = tags
    # TODO: look for parameters too
    if host in {"youtu.be", "youtube.com", "vimeo.com"}:
        return Category.VIDEO

    return None


def __derive_ask_tell(
    platform: Platform,
    title_tokens: list[str],
    host: str,
    path_components: list[str],
    tags: set[str],
) -> Category | None:
    _ = path_components
    _ = tags
    if (
        platform == Platform.HACKER_NEWS
        and len(title_tokens) >= 2
        and (
            title_tokens[:2] == ["ask", "hn"] or title_tokens[-1].endswith("?")
        )
        and not host
    ):
        return Category.ASK_PLATFORM

    if (
        platform == Platform.HACKER_NEWS
        and title_tokens[:2] == ["tell", "hn"]
        and not host
    ):
        return Category.TELL_PLATFORM
    return None


derive_functions = [
    __derive_release,
    __derive_project,
    __derive_video,
    __derive_ask_tell,
]
