# Generated by Django 4.0a1 on 2022-10-04 19:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0056_alter_ad_week_week_alter_ad_week_year"),
    ]

    operations = [
        migrations.AddField(
            model_name="ad",
            name="comments",
            field=models.TextField(blank=True, null=True),
        ),
    ]
