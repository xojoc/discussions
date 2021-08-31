from django.urls import path
from . import views

app_name = 'web'


def sentry_trigger_error(request):
    _ = 1 / 0


urlpatterns = [
    path('', views.index, name='index'),
    path('sentry-debug/', sentry_trigger_error)
]
