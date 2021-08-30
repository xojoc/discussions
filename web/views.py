from web import models, discussions
from django.shortcuts import render
import itertools


def discussions_context(url):
    ctx = {}

    ctx['statistics'] = models.Statistics.all_statistics()

    ctx['url'] = url or ''
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
    ctx = discussions_context(request.GET.get('url'))

    return render(request, "web/discussions.html", {'ctx': ctx})
