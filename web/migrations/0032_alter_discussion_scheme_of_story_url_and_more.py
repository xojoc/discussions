# Generated by Django 4.0a1 on 2022-01-04 18:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0031_remove_discussion_gin_discussion_title_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="discussion",
            name="scheme_of_story_url",
            field=models.CharField(max_length=25, null=True),
        ),
        migrations.AlterField(
            model_name="discussion",
            name="schemeless_story_url",
            field=models.CharField(max_length=100000, null=True),
        ),
        migrations.AlterField(
            model_name="discussion",
            name="title",
            field=models.CharField(max_length=2048, null=True),
        ),
    ]
