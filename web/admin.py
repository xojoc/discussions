from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path
from . import models


class StatisticsAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('statistics/',
                 self.admin_site.admin_view(self.statistics_view)),
        ]
        return my_urls + urls

    def statistics_view(self, request):
        # ...
        context = dict(
            # Include common variables for rendering the admin template.
            self.admin_site.each_context(request),
            # Anything else you want in the context...
            test="value",
        )

        return TemplateResponse(request, "web/admin_statistics.html", context)


admin.site.register([models.Discussion, models.Tweet, models.Statistics])
