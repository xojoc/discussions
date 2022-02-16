from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path
from . import models


class StatisticsAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "statistics/", self.admin_site.admin_view(self.statistics_view)
            ),
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


class DiscussionAdmin(admin.ModelAdmin):
    list_display = [
        "platform_id",
        "created_at",
        "tags",
        "normalized_tags",
        "comment_count",
        "score",
        "title",
        "normalized_title",
    ]
    # list_filter = [
    #     "platform",
    # ]
    search_fields = (
        "title",
        "tags",
    )


admin.site.register(models.Discussion, DiscussionAdmin)

admin.site.register(
    [models.Subscriber, models.APIClient, models.Tweet, models.Statistics]
)
