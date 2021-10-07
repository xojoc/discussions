from web import models, discussions, serializers
from django.shortcuts import render
import itertools
from django.core.cache import cache
# from web import statistics
from rest_framework import viewsets, views as rest_views
from rest_framework import permissions
from rest_framework.response import Response as RESTResponse
from django.contrib.auth.models import User, Group


def discussions_context_cached(url):
    if not url:
        return discussions_context(url)

    key = 'discussions_context:' + url
    touch_key = 'touch:' + key
    ctx = cache.get(key)
    if ctx:
        if cache.get(touch_key):
            cache.touch(key, 30)
    else:
        ctx = discussions_context(url)
        if ctx and ctx['grouped_discussions']:
            cache.set(key, ctx, 60)
            cache.set(touch_key, 1, timeout=60 * 3)

    return ctx


def discussions_context(url):
    ctx = {}

    ctx['statistics'] = models.Statistics.all_statistics()

    if url and not (url.startswith('http://') or url.startswith('https://')):

        ctx['absolute_url'] = 'https://' + url
    else:
        ctx['absolute_url'] = url

    ctx['url'] = url
    ctx['url'] = ctx['url'].strip()
    ctx['display_discussions'] = False
    ctx['nothing_found'] = False
    ctx['hn'] = None
    ctx['lobsters'] = None
    ctx['reddit'] = None
    ctx['title'] = ""
    if not ctx['url']:
        return ctx
    ctx['display_discussions'] = True
    uds, tds, cu, rcu = models.Discussion.of_url_or_title(ctx['url'])
    tds = tds[:11]

    ctx['canonical_url'] = cu

    # ds = sorted(ds, key=lambda x: x.platform_order)
    ctx['discussions'] = uds
    ctx['title_discussions'] = tds

    # We have to convert the iterator to a list, see: https://stackoverflow.com/a/16171518
    ctx['grouped_discussions'] = [
        (platform, models.Discussion.platform_name(platform),
         models.Discussion.platform_url(
             platform,
             preferred_external_url=discussions.PreferredExternalURL.Standard),
         models.Discussion.platform_tag_url(
             platform,
             preferred_external_url=discussions.PreferredExternalURL.Standard),
         list(uds))
        for platform, uds in itertools.groupby(uds, lambda x: x.platform)
    ]

    if uds:
        ctx['title'] = uds[0].title
    else:
        ctx['display_discussions'] = False
        ctx['nothing_found'] = True

    return ctx


def index(request):
    url = request.GET.get('url')
    url = (url or '').lower()
    ctx = discussions_context_cached(url)

    return render(request, "web/discussions.html", {'ctx': ctx})


class APIUserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = serializers.UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class APIGroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all()
    serializer_class = serializers.GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


class APIDiscussionsOfURLView(rest_views.APIView):
    def get(self, request):
        url = request.GET.get('url')
        url = (url or '').lower()
        ctx = discussions_context_cached(url)

        results = serializers.DiscussionsOfURLSerializer(
            ctx.get('discussions')).data
        return RESTResponse(results)
