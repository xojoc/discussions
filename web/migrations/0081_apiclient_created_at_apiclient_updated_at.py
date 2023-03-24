# Generated by Django 4.1.7 on 2023-03-24 13:50

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("web", "0080_mention_exclude_platforms"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiclient",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="apiclient",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
