from web import models, discussions, serializers, twitter, util, forms
from django.shortcuts import render
import itertools
from django.core.cache import cache
from rest_framework import viewsets, views as rest_views
from rest_framework import permissions
from rest_framework.response import Response as RESTResponse
from django.contrib.auth.models import User, Group
from django.http import HttpResponsePermanentRedirect
from discussions import settings
from urllib.parse import unquote as url_unquote
from urllib.parse import quote
import logging
from django_redis import get_redis_connection


logger = logging.getLogger(__name__)


def __log_query(q):
    if not q:
        return

    q = q.strip().lower()

    r = get_redis_connection()
    if q.startswith('http://') or q.startswith('https://'):
        r.zincrby('discussions:stats:query:url', 1, q)
    else:
        r.zincrby('discussions:stats:query:search', 1, q)


def discussions_context_cached(q):
    if not q:
        return discussions_context(q)

    suffix = (q or '').lower().strip()

    key = 'discussions_context:' + suffix
    touch_key = 'touch:' + key
    ctx = cache.get(key)

    if ctx:
        if cache.get(touch_key):
            cache.touch(key, 30)
    else:
        ctx = discussions_context(q)
        if ctx and ctx['nothing_found'] is False:
            cache.set(key, ctx, 60)
            cache.set(touch_key, 1, timeout=60 * 3)

    return ctx


def discussions_context(q):
    ctx = {}

    q = (q or '').strip()

    url = (q or '').lower().strip()

    # ctx['statistics'] = models.Statistics.all_statistics()

    if url and not (url.startswith('http://') or url.startswith('https://')):
        ctx['absolute_url'] = 'https://' + q
    else:
        ctx['absolute_url'] = q

    if q:
        ctx['link_canonical_url'] = util.discussions_canonical_url(q)

    ctx['original_query'] = q
    ctx['url'] = url
    ctx['display_discussions'] = False
    ctx['nothing_found'] = False
    ctx['title'] = ""
    if not ctx['url']:
        return ctx
    ctx['display_discussions'] = True
    uds, cu, rcu = models.Discussion.of_url_or_title(ctx['url'])

    ctx['sql_query'] = ''
    if uds is not None:
        ctx['sql_query'] = str(uds.query)

    try:
        uds = list(uds)
    except Exception as e:
        logger.warn(e)
        uds = []

    # tds = tds[:11]
    tds = None

    ctx['canonical_url'] = cu

    # ds = sorted(ds, key=lambda x: x.platform_order)
    ctx['discussions'] = uds
    ctx['title_discussions'] = tds

    uds.sort(key=lambda i: i.platform)

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

    if q.startswith('http://') or\
       q.startswith('https://'):

        ctx['resource'] = models.Resource.by_url(cu)
        if ctx['resource']:
            ctx['title'] = ctx['resource'].title
            ctx['inbound_resources'] = ctx['resource'].inbound_resources()
            for res in ctx['inbound_resources']:
                res.discussions_comment_count = res.discussions_comment_count()

    if not ctx.get('title'):
        if uds and\
           (q.startswith('http://') or q.startswith('https://')):

            ctx['title'] = uds[0].title
        else:
            ctx['title'] = ctx['original_query']

    if not uds:
        ctx['display_discussions'] = False

    if not uds and not tds:
        ctx['nothing_found'] = True

    return ctx


def get_submit_links(request, ctx):
    q = ctx['original_query']
    if not (q.lower().startswith('http://') or q.lower().startswith('https://')):
        return

    url = quote(q)

    ctx['submit_title'] = request.GET.get('submit_title') or ctx['title'] or ''
    t = quote(ctx.get('submit_title'))

    submit_links = {'Hacker News': f'https://news.ycombinator.com/submitlink?u={url}&t={t}',
                    'Reddit': f'https://www.reddit.com/submit?url={url}&title={t}',
                    'Lobsters': f'https://lobste.rs/stories/new?url={url}&title={t}',
                    'Barnacles': f'https://barnacl.es/stories/new?url={url}&title={t}',
                    'Gambero': f'https://gambe.ro/stories/new?url={url}&title={t}'
                    }

    ctx['submit_links'] = submit_links

    ctx['submit_links_visible'] = False
    if ctx['nothing_found']:
        ctx['submit_links_visible'] = True


def index(request, path_q=None):
    host = request.get_host().partition(":")[0]
    if not request.path.startswith('/.well-known/'):
        if host != 'localhost' and host != '127.0.0.1' and host != settings.APP_DOMAIN:
            r = 'https://' + settings.APP_DOMAIN + request.get_full_path()
            return HttpResponsePermanentRedirect(r)

    if path_q:
        q = url_unquote(request.get_full_path()[len('/q/'):])
    else:
        q = request.GET.get('url')
        if not q:
            q = request.GET.get('q')

    q = q or ''

    ctx = discussions_context_cached(q)

    get_submit_links(request, ctx)

    ctx['form'] = forms.QueryForm(request.GET)
    ctx['form'].fields['tags'].choices = [('tag', 'asdf'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ('tag2', 'fdsa'),
                                          ]

    try:
        __log_query(q)
    except Exception as e:
        logger.warn(e)

    response = render(request, "web/discussions.html", {'ctx': ctx})

    if ctx['nothing_found']:
        response.status_code = 404

    return response


def statistics(request):
    ctx = {'statistics': models.Statistics.all_statistics()}
    return render(request, "web/statistics.html", {'ctx': ctx})


def __social_context(request):
    bots = []
    for bot_name, bot_values in twitter.configuration['bots'].items():
        bot = {'link': f"https://twitter.com/{ bot_name }",
               'link_title': f"{ bot_values['topic'] } Twitter bot",
               'nick': f"@{ bot_name }",
               'description': f"{ bot_values['description'] }"}
        bots.append(bot)

    return {'twitter_bots': bots}


def social(request):
    ctx = __social_context(request)
    return render(request, "web/social.html", {'ctx': ctx})


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
