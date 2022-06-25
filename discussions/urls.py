import debug_toolbar
from django.contrib import admin
from django.contrib.sitemaps.views import index as sitemap_index
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.decorators.cache import cache_page
from django.views.generic.base import TemplateView
from web import api_v0, sitemaps

from . import settings

sitemaps_dict = {
    "discussions": sitemaps.DiscussionsSitemap,
    "static": sitemaps.StaticViewSitemap,
    "weekly": sitemaps.WeeklySitemap,
}

urlpatterns = [
    path("", include("web.urls")),
    path("admin/", admin.site.urls),
    # path("accounts/", include("allauth.urls")),
    path("__debug__/", include(debug_toolbar.urls)),
    path("api/v0/", api_v0.api.urls),
    path(
        "sitemap.xml",
        cache_page(60 * 60 * 24 * 7, key_prefix="sitemap:")(sitemap_index),
        {"sitemaps": sitemaps_dict, "sitemap_url_name": "sitemaps"},
    ),
    path(
        "sitemap-<str:section>.xml",
        cache_page(60 * 60 * 24 * 7, key_prefix="sitemap:")(sitemap),
        {"sitemaps": sitemaps_dict},
        name="sitemaps",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
            extra_context={
                "sitemap_url": "https://"
                + settings.APP_DOMAIN
                + "/sitemap.xml"
            },
        ),
    ),
    path(
        "2e5ddde867414c0fb0973d5d52044653.txt",
        TemplateView.as_view(
            template_name="2e5ddde867414c0fb0973d5d52044653.txt",
            content_type="text/plain",
        ),
    ),
]
