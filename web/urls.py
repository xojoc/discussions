from django.urls import path
from django.views.generic.base import RedirectView
from . import views
from django.views.generic import TemplateView

# from .api import api

app_name = "web"


def sentry_trigger_error(request):
    _ = 1 / 0


urlpatterns = [
    path("", views.index, name="index"),
    path("q/<path:path_q>", views.index, name="index"),
    path("weekly/", views.weekly_index, name="weekly_index"),
    path(
        "weekly/confirm_email/",
        views.weekly_confirm_email,
        name="weekly_confirm_email",
    ),
    path("weekly/<slug:topic>/", views.weekly_topic, name="weekly_topic"),
    path(
        "weekly/<slug:topic>/<int:year>/<int:week>/",
        views.weekly_topic_week,
        name="weekly_topic_week",
    ),
    path("sentry-debug/", sentry_trigger_error),
    path("social/", views.social),
    path("twitter/", RedirectView.as_view(url="/social/")),
    path("statistics/", views.statistics),
    path(
        "extension/", TemplateView.as_view(template_name="web/extension.html")
    ),
    path("website/", TemplateView.as_view(template_name="web/website.html")),
    path(
        "bookmarklet/",
        TemplateView.as_view(template_name="web/bookmarklet.html"),
    ),
    path(
        "opensearch.xml",
        TemplateView.as_view(
            template_name="web/opensearch.xml",
            content_type="application/opensearchdescription+xml",
        ),
    ),
]
