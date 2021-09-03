from web import models, discussions
from django.shortcuts import render
import itertools
from django.core.cache import cache
from web import statistics


def discussions_context_cached(url):
    if not url:
        return discussions_context(url)

    key = 'discussions_context:' + url
    touch_key = 'touch:' + key
    ctx = cache.get(key)
    if ctx:
        if cache.get(touch_key):
            cache.touch(key)
    else:
        ctx = discussions_context(url)
        if ctx and ctx['grouped_discussions']:
            cache.set(key, ctx)
            cache.set(touch_key, 1, timeout=60*15)

    return ctx


def discussions_context(url):
    ctx = {}

    _ = list(statistics.discussions_top_domains())
    _ = list(statistics.discussions_top_stories())
    _ = list(statistics.discussions_platform_statistics())

    ctx['statistics'] = models.Statistics.all_statistics()

    if url and not (url.startswith('http://') or
                    url.startswith('https://')):

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
    ds, cu, rcu = models.Discussion.of_url(ctx['url'])
    ctx['canonical_url'] = cu

    # ds = sorted(ds, key=lambda x: x.platform_order)
    ctx['discussions'] = ds

    # We have to convert the iterator to a list, see: https://stackoverflow.com/a/16171518
    ctx['grouped_discussions'] = [(platform,
                                   models.Discussion.platform_name(platform),
                                   models.Discussion.platform_url(
                                       platform, preferred_external_url=discussions.PreferredExternalURL.Standard),
                                   models.Discussion.platform_tag_url(
                                       platform, preferred_external_url=discussions.PreferredExternalURL.Standard),
                                   list(ds))
                                  for platform, ds in itertools.groupby(ds, lambda x: x.platform)]

    if ds:
        ctx['title'] = ds[0].title
    else:
        ctx['display_discussions'] = False
        ctx['nothing_found'] = True

    return ctx


def index(request):
    url = request.GET.get('url')
    url = (url or '').lower()
    ctx = discussions_context_cached(url)

    return render(request, "web/discussions.html", {'ctx': ctx})
