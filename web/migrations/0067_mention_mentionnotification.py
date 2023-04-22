# Generated by Django 4.0.8 on 2022-10-06 23:13

import django.contrib.postgres.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0066_discussion_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="Mention",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rule_name", models.CharField(max_length=255)),
                ("url_pattern", models.TextField()),
                ("title_pattern", models.TextField(blank=True)),
                ("platforms", django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, choices=[("h", "Hacker News"), ("l", "Lobsters")], max_length=1), blank=True, null=True, size=None)),
                ("subreddits_only", django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, choices=[("h", "Hacker News"), ("l", "Lobsters")], max_length=255), blank=True, null=True, size=None)),
                ("subreddits_exclude", django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, choices=[("h", "Hacker News"), ("l", "Lobsters")], max_length=255), blank=True, null=True, size=None)),
                ("min_comments", models.PositiveIntegerField(default=0)),
                ("min_score", models.IntegerField(default=0)),
                ("disabled", models.BooleanField(default=False)),
                ("entry_created_at", models.DateTimeField(auto_now_add=True)),
                ("entry_updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="MentionNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_sent", models.BooleanField(default=False)),
                ("entry_created_at", models.DateTimeField(auto_now_add=True)),
                ("entry_updated_at", models.DateTimeField(auto_now=True)),
                ("discussion", models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, to="web.discussion")),
                ("mention", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="web.mention")),
            ],
        ),
    ]
