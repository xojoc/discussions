# Generated by Django 4.0a1 on 2022-10-04 22:18

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0061_ad_entry_created_at_ad_entry_updated_at_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ad",
            name="topics",
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, choices=[("apl", "APL"), ("candcpp", "C & C++"), ("compsci", "Computer science"), ("devops", "DevOps"), ("erlang", "Erlang & Elixir"), ("golang", "Golang"), ("hackernews", "Hacker News"), ("haskell", "Haskell"), ("java", "Java"), ("laarc", "Laarc"), ("lisp", "Lisp & Scheme"), ("nim", "Nim"), ("php", "PHP"), ("programming", "Software Development"), ("python", "Python"), ("ruby", "Ruby"), ("rust", "Rust"), ("unix", "Unix"), ("webdev", "Web Development"), ("zig", "Zig")], max_length=255), blank=True, help_text="Ads are always reviewed manually and only ads relevant to the topic are approved", null=True, size=None),
        ),
    ]
