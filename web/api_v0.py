from datetime import date
from typing import List

from django.core.cache import cache
from ninja import ModelSchema, NinjaAPI, Schema
from ninja.security import HttpBearer

from . import models, util, api_statistics

api = NinjaAPI(version="v0")
api.title = "Discussions and comments API"

api.description = """
<p>
To get a Bearer token <a href="/account/signup/" title="Sign Up">create a free account</a>.
</p>
<p>
If you just want to try out the API then use the following token: <strong>test</strong>.
</p>
"""

cache_prefix = "api"


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        key = f"{cache_prefix}:token:{token}"

        api_client = cache.get(key)
        if api_client:
            return api_client

        timeout = 30 * 60
        try:
            api_client = models.APIClient.objects.get(
                token=token, limited=False
            )
            cache.set(key, api_client, timeout)
            return api_client
        except models.APIClient.DoesNotExist:
            return None


auth_bearer = AuthBearer()


class Discussion(ModelSchema):
    class Config:
        model = models.Discussion
        model_fields = ["created_at", "title", "comment_count", "score"]

    platform: str
    id: str
    story_url: str = None
    tags: List[str] = None
    normalized_tags: List[str] = None
    discussion_url: str
    subreddit: str = None


class DiscussionCounts(Schema):
    total_comments: int = 0
    total_score: int = 0
    total_discussions: int = 0
    last_discussion: date = None
    first_discussion: date = None
    story_url: str = None
    discussions_url: str = None
    articles_count: int = 0
    comments_by_platform: dict[str, int] = {}
    tags: list[str] = []


class Message(Schema):
    message: str


@api.get(
    "/discussions/url/{path:url}",
    response={200: List[Discussion]},
    auth=auth_bearer,
)
def get_discussions(request, url: str, only_relevant_stories: bool = True):
    """Get all discussions for a given URL."""

    api_statistics.track(request)

    suffix = (url or "").lower().strip()
    key = f"{cache_prefix}:get_discussions:{only_relevant_stories}:{suffix}"
    touch_key = "touch:" + key

    ds = cache.get(key)

    timeout = 5 * 60

    if ds:
        if cache.get(touch_key):
            cache.touch(key, timeout)
        return ds

    ds, _, _ = models.Discussion.of_url(url, only_relevant_stories)

    if ds:
        cache.set(key, ds, timeout)
        cache.set(touch_key, 1, timeout=timeout * 3)

    return ds


@api.api_operation(
    ["OPTIONS"],
    "/discussions/url/{path:url}",
    response={200: List[Discussion]},
    include_in_schema=False,
)
def options_get_discussions(
    request, url: str, only_relevant_stories: bool = True
):
    return []


@api.get(
    "/discussion_counts/url/{path:url}",
    response={200: DiscussionCounts},
    auth=auth_bearer,
)
def get_discussion_counts(request, url: str):
    """Get discussion counts for a given URL."""

    api_statistics.track(request)

    suffix = (url or "").lower().strip()
    key = f"{cache_prefix}:get_discussion_counts:{suffix}"
    touch_key = "touch:" + key

    dcs = cache.get(key)

    timeout = 5 * 60

    if dcs:
        if cache.get(touch_key):
            cache.touch(key, timeout)
        return dcs

    dcs = DiscussionCounts()

    ds, _, _ = models.Discussion.of_url(url, True)

    dcs.story_url = url
    dcs.discussions_url = util.discussions_url(url)

    dcs.tags = []

    for d in ds:
        dcs.total_comments += d.comment_count
        dcs.total_score += d.score
        dcs.total_discussions += 1
        if not dcs.first_discussion:
            dcs.first_discussion = d.created_at
        else:
            dcs.first_discussion = min(dcs.first_discussion, d.created_at)

        if not dcs.last_discussion:
            dcs.last_discussion = d.created_at
        else:
            dcs.last_discussion = max(dcs.last_discussion, d.created_at)

        dcs.comments_by_platform[d.platform] = (
            dcs.comments_by_platform.get(d.platform, 0) + d.comment_count
        )

        if d.platform == "r":
            platform = d.platform + "/" + d.subreddit
            dcs.comments_by_platform[platform] = (
                dcs.comments_by_platform.get(platform, 0) + d.comment_count
            )

        dcs.tags.extend(d.normalized_tags or [])

    dcs.tags = sorted(set(dcs.tags))

    dcs.articles_count = 0
    r = models.Resource.by_url(url)
    if r is not None:
        ir = r.inbound_resources()
        if ir is not None:
            dcs.articles_count = ir.count()

    if dcs:
        cache.set(key, dcs, timeout)
        cache.set(touch_key, 1, timeout=timeout * 3)

    return dcs


@api.api_operation(
    ["OPTIONS"],
    "/discussion_counts/url/{path:url}",
    response={200: DiscussionCounts},
    include_in_schema=False,
)
def options_get_discussion_counts(request, url: str):
    return {}


class Platform(Schema):
    code: str
    name: str
    url: str


@api.get(
    "/platforms",
    response={200: List[Platform]},
    auth=auth_bearer,
)
def platforms(request):
    """All platforms on which discussions are tracked at the moment."""

    api_statistics.track(request)

    pfs = models.Discussion.platforms()
    return [{"code": k, "name": v[0], "url": v[1]} for k, v in pfs.items()]
