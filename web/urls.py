from django.urls import path
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

from . import views

app_name = "web"


def sentry_trigger_error(request):
    _ = 1 / 0


urlpatterns = [
    path("", views.index, name="index"),
    path("q/<path:path_q>", views.index, name="index"),
    path("s/<str:platform_id>", views.short_url, name="short_url"),
    path("weekly/", views.weekly_index, name="weekly_index"),
    path(
        "weekly/confirm_email/",
        views.weekly_confirm_email,
        name="weekly_confirm_email",
    ),
    path(
        "weekly/confirm_unsubscription/",
        views.weekly_confirm_unsubscription,
        name="weekly_confirm_unsubscription",
    ),
    path("weekly/<slug:topic>/", views.weekly_topic, name="weekly_topic"),
    path(
        "weekly/<slug:topic>/<int:year>/<int:week>/",
        views.weekly_topic_week,
        name="weekly_topic_week",
    ),
    path("sentry-debug/", sentry_trigger_error),
    path("social/", views.social, name="social"),
    path("twitter/", RedirectView.as_view(url="/social/")),
    path("statistics/", views.statistics, name="statistics"),
    path(
        "extension/",
        TemplateView.as_view(template_name="web/extension.html"),
        name="extension",
    ),
    path(
        "website/",
        TemplateView.as_view(template_name="web/website.html"),
        name="website",
    ),
    path(
        "bookmarklet/",
        TemplateView.as_view(template_name="web/bookmarklet.html"),
        name="bookmarklet",
    ),
    path(
        "search/",
        TemplateView.as_view(template_name="web/search.html"),
        name="search",
    ),
    path(
        "opensearch.xml",
        TemplateView.as_view(
            template_name="web/opensearch.xml",
            content_type="application/opensearchdescription+xml",
        ),
    ),
]
