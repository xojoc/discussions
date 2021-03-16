from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('', include('web.urls')),
    path('admin/', admin.site.urls),
    url(r'^admin/statuscheck/', include('celerybeat_status.urls', namespace='celerybeat_status')),
]
