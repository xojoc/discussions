# Generated by Django 4.0a1 on 2021-12-24 00:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0020_tweet_bot_names"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="discussion",
            name="web_discuss_schemel_e43bc8_idx",
        ),
        migrations.RemoveIndex(
            model_name="discussion",
            name="web_discuss_canonic_da28e0_idx",
        ),
        migrations.RemoveIndex(
            model_name="discussion",
            name="web_discuss_canonic_6b6a46_idx",
        ),
        migrations.AddIndex(
            model_name="discussion",
            index=models.Index(fields=["schemeless_story_url"], name="index_schemeless_story_url", opclasses=["varchar_pattern_ops"]),
        ),
        migrations.AddIndex(
            model_name="discussion",
            index=models.Index(fields=["canonical_story_url"], name="index_canonical_story_url", opclasses=["varchar_pattern_ops"]),
        ),
        migrations.AddIndex(
            model_name="discussion",
            index=models.Index(fields=["canonical_redirect_url"], name="index_canonical_redirect_url", opclasses=["varchar_pattern_ops"]),
        ),
    ]
