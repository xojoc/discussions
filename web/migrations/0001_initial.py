# Generated by Django 3.1.7 on 2021-03-07 11:15

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("web", "0000_create_extensions"),
    ]

    operations = [
        migrations.CreateModel(
            name="Discussion",
            fields=[
                (
                    "platform_id",
                    models.CharField(
                        max_length=50, primary_key=True, serialize=False
                    ),
                ),
                ("platform", models.CharField(max_length=1)),
                ("created_at", models.DateTimeField(null=True)),
                ("scheme_of_story_url", models.CharField(max_length=25)),
                ("schemeless_story_url", models.CharField(max_length=100000)),
                (
                    "canonical_story_url",
                    models.CharField(blank=True, max_length=2000, null=True),
                ),
                (
                    "canonical_redirect_url",
                    models.CharField(
                        blank=True, default=None, max_length=2000, null=True
                    ),
                ),
                ("title", models.CharField(max_length=2048)),
                ("comment_count", models.IntegerField(default=0)),
                ("score", models.IntegerField(default=0)),
                (
                    "tags",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            blank=True, max_length=255
                        ),
                        blank=True,
                        null=True,
                        size=None,
                    ),
                ),
                ("archived", models.BooleanField(default=False)),
            ],
        ),
    ]
