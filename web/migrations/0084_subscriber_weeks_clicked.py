# Generated by Django 4.1.7 on 2023-04-01 09:56

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("web", "0083_alter_mention_disabled_alter_mention_keywords_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriber",
            name="weeks_clicked",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=6), null=True, size=None,
            ),
        ),
    ]
