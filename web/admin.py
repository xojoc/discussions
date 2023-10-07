from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path

from . import models


class StatisticsAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "statistics/",
                self.admin_site.admin_view(self.statistics_view),
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
        "unsubscribed_from",
        "email",
        "subscribed_from",
        "entry_created_at",
        "suspected_spam",
    ]
    list_filter = [
        "confirmed",
        "unsubscribed",
        "unsubscribed_from",
        "subscribed_from",
        "topic",
        "suspected_spam",
    ]
    search_fields = ("email", "verification_code")
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
        "last_login",
    ]
    list_filter = [
        "premium_active",
        "premium_cancelled",
        "is_active",
    ]
    search_fields = ("complete_name", "email")
    ordering = [
        "-date_joined",
    ]


class MentionAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "rule_name",
        "user",
        "base_url",
        "keywords",
        "exclude_platforms",
        "disabled",
        "entry_created_at",
    ]
    list_filter = ["disabled"]
    ordering = ["-entry_created_at"]


class MentionNotificationAdmin(admin.ModelAdmin):
    list_display = [
        "mention",
        "get_user",
        "email_sent",
        "email_sent_at",
        "entry_created_at",
        "discussion",
    ]
    list_filter = ["email_sent"]
    ordering = ["-entry_created_at"]
    raw_id_fields = ["discussion"]

    @admin.display(ordering="mention__user", description="User")
    def get_user(self, obj):
        return obj.mention.user


class APIClientAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "name",
        "customuser",
        "limited",
        "email",
        "url",
        "get_statistics",
    ]
    list_filter = ["limited"]
    search_fields = ("name", "token", "email", "url")
    ordering = [
        "-created_at",
    ]


admin.site.register(models.Discussion, DiscussionAdmin)
admin.site.register(models.Resource)
admin.site.register(models.Subscriber, SubscriberAdmin)

admin.site.register(models.APIClient, APIClientAdmin)
admin.site.register([models.Tweet, models.Statistics])

admin.site.register(models.CustomUser, CustomUserAdmin)
admin.site.register([models.AD])

admin.site.register(models.Mention, MentionAdmin)
admin.site.register(models.MentionNotification, MentionNotificationAdmin)
