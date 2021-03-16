from django.contrib import admin
from django.urls import re_path, include, path


urlpatterns = [
    path('', include('web.urls')),
    path('admin/', admin.site.urls),
    re_path(r'^admin/statuscheck/', include('celerybeat_status.urls', namespace='celerybeat_status')),
]
