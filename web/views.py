from django.shortcuts import render
import datetime
from django.http import HttpResponse
from . import models
from django.utils.timezone import make_aware

def index(request):
    now = datetime.datetime.now()
    html = '<html><body>It is now %s.</body></html>' % now

    models.Discussion(
        platform_id='z',
        comment_count=3,
        score=4,
        created_at=make_aware(now),
        scheme_of_story_url='http',
        schemeless_story_url='xojoc.pw',
        canonical_story_url=None,
        title='Title').save()

    return HttpResponse(html)
