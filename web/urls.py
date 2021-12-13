from django.urls import include, path
from . import views
from rest_framework import routers
from django.views.generic import TemplateView

app_name = 'web'


def sentry_trigger_error(request):
    _ = 1 / 0


router = routers.DefaultRouter()
router.register(r'users', views.APIUserViewSet)
router.register(r'groups', views.APIGroupViewSet)


urlpatterns = [
    path('', views.index, name='index'),
    path('q/<path:path_q>', views.index, name='index'),
    path('api/', include((router.urls, 'web'), namespace='api')),
    path('api/discussions',
         views.APIDiscussionsOfURLView.as_view(),
         name='discussions'),
    path('sentry-debug/', sentry_trigger_error),
    path('twitter/', TemplateView.as_view(template_name="web/twitter.html"))
]
