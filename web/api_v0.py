from ninja import NinjaAPI, ModelSchema, Schema
from ninja.security import HttpBearer
from . import models, util
from typing import List
from datetime import date


api = NinjaAPI(version='v0')
api.title = "Discussions API"
api.description = """<p>
API for <a href="https://discu.eu" title="Discussions around the web">discu.eu</a>.
</p>
<p>
To get a Bearer token please drop me an email: hi@xojoc.pw
</p>
"""


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            return models.APIClient.objects.get(
                token=token,
                limited=False)
        except models.APIClient.DoesNotExist:
            return None


auth_bearer = AuthBearer()


class Discussion(ModelSchema):
    class Config:
        model = models.Discussion
        model_fields = ['created_at', 'title',
                        'comment_count', 'score']

    platform: str
    id: str
    story_url: str = None
    tags: List[str] = None
    normalized_tags: List[str] = None
    discussion_url: str
    subreddit: str = None


class DiscussionCounts(Schema):
    total_comments: int
    total_score: int
    total_discussions: int
    last_discussion: date = None
    first_discussion: date = None
    story_url: str = None
    discussions_url: str = None
    articles_count: int


class Message(Schema):
    message: str


@api.get('/discussions/url/{path:url}',
         response={200: List[Discussion]},
         auth=auth_bearer)
def get_discussions(request, url: str, only_relevant_stories: bool = True):
    """Get all discussions for a given URL."""
    ds, cu, rcu = models.Discussion.of_url(url, only_relevant_stories)
    return ds


@api.get('/discussion_counts/url/{path:url}',
         response={200: DiscussionCounts},
         auth=auth_bearer)
def get_discussion_counts(request, url: str):
    """Get discussion counts for a given URL."""
    dcs, cu, rcu = models.Discussion.counts_of_url(url)
    if dcs:
        dcs['discussions_url'] = util.discussions_url(url)
    dcs['articles_count'] = 0
    r = models.Resource.by_url(url)
    if r is not None:
        ir = r.inbound_resources()
        if ir is not None:
            dcs['articles_count'] = ir.count()
    return dcs
