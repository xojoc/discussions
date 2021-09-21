from django.contrib import admin
from django.urls import include, path
import debug_toolbar


urlpatterns = [
    path('', include('web.urls')),
    path('admin/', admin.site.urls),
    path('__debug__/', include(debug_toolbar.urls)),

    path('api-auth/', include('rest_framework.urls'))
]
