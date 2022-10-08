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
    search_fields = (
        "title",
        "tags",
    )


class SubscriberAdmin(admin.ModelAdmin):
    list_display = [
        "topic",
        "confirmed",
        "unsubscribed",
        "unsubscribed_at",
        "email",
        "subscribed_from",
        "entry_created_at",
    ]
    list_filter = ["confirmed", "unsubscribed", "topic"]
    ordering = [
        "-entry_created_at",
    ]


class CustomUserAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "premium_active",
        "premium_active_from",
        "premium_cancelled",
        "premium_cancelled_on",
        "complete_name",
        "email",
        "email_verified",
        "is_active",
        "date_joined",
    ]
    list_filter = ["premium_active", "premium_cancelled", "is_active"]
    search_fields = ("complete_name",)
    ordering = [
        "-date_joined",
    ]


class MentionAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "rule_name",
        "user",
        "base_url",
        "keyword",
        "platforms",
        "disabled",
        "entry_created_at",
    ]
    list_filter = ["disabled"]
    ordering = ["-entry_created_at"]


class MentionNotificationAdmin(admin.ModelAdmin):
    list_display = [
        "mention",
        "discussion",
        "email_sent",
        "email_sent_at",
        "entry_created_at",
    ]
    list_filter = ["email_sent"]
    ordering = ["-entry_created_at"]
    raw_id_fields = ["discussion"]


admin.site.register(models.Discussion, DiscussionAdmin)
admin.site.register(models.Subscriber, SubscriberAdmin)

admin.site.register([models.APIClient, models.Tweet, models.Statistics])

admin.site.register(models.CustomUser, CustomUserAdmin)
admin.site.register([models.AD])

admin.site.register(models.Mention, MentionAdmin)
admin.site.register(models.MentionNotification, MentionNotificationAdmin)
