# Generated by Django 4.0a1 on 2021-12-28 19:37

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0023_alter_tweet_bot_names"),
    ]

    operations = [
        migrations.CreateModel(
            name="Resource",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("scheme", models.CharField(max_length=25)),
                ("url", models.CharField(blank=True, default=None, max_length=100000, null=True)),
                ("canonical_url", models.CharField(blank=True, max_length=100000, null=True)),
                ("title", models.CharField(max_length=2048, null=True)),
                ("normalized_tags", django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, max_length=255), blank=True, null=True, size=None)),
                ("clean_html", models.TextField(null=True)),
                ("excerpt", models.TextField(null=True)),
                ("last_fetch", models.DateTimeField(null=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="resource",
            index=models.Index(fields=["url"], name="index_url", opclasses=["varchar_pattern_ops"]),
        ),
        migrations.AddIndex(
            model_name="resource",
            index=models.Index(fields=["canonical_url"], name="index_canonical_url", opclasses=["varchar_pattern_ops"]),
        ),
    ]
