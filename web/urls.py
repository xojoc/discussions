from django.urls import include, path
from . import views
from rest_framework import routers


app_name = 'web'


def sentry_trigger_error(request):
    _ = 1 / 0


router = routers.DefaultRouter()
router.register(r'users', views.APIUserViewSet)
router.register(r'groups', views.APIGroupViewSet)

urlpatterns = [
    path('', views.index, name='index'),
    path('api/', include((router.urls, 'web'), namespace='api')),
    path('api/discussions', views.APIDiscussionsOfURLView, name='discussions'),
    path('sentry-debug/', sentry_trigger_error)
]
