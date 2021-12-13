from django.contrib import admin
from django.urls import include, path
import debug_toolbar
from django.contrib.sitemaps.views import sitemap, index as sitemap_index
from web import sitemaps
from django.views.generic.base import TemplateView
from . import settings
from django.views.decorators.cache import cache_page

sitemaps_dict = {'discussions': sitemaps.DiscussionsSitemap}

urlpatterns = [
    path('', include('web.urls')),
    path('admin/', admin.site.urls),
    path('__debug__/', include(debug_toolbar.urls)),

    path('api-auth/', include('rest_framework.urls')),


    path('sitemap.xml',
         cache_page(60 * 60 * 24 * 7)(sitemap_index), {
             'sitemaps': sitemaps_dict, 'sitemap_url_name': 'sitemaps'}),

    path('sitemap-<str:section>.xml',
         cache_page(60 * 60 * 24 * 7)(sitemap), {'sitemaps': sitemaps_dict},
         name='sitemaps'),

    path("robots.txt", TemplateView.as_view(
        template_name="robots.txt",
        content_type="text/plain",
        extra_context={'sitemap_url': 'https://' +
                       settings.APP_DOMAIN + '/sitemap.xml'}
    )),
]
