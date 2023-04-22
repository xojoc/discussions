# Generated by Django 4.0a1 on 2022-01-05 13:11

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0032_alter_discussion_scheme_of_story_url_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MastodonPost",
            fields=[
                ("post_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("bot_names", django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, default=list, null=True, size=None)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("discussions", models.ManyToManyField(to="web.Discussion")),
            ],
        ),
    ]
