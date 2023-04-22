# Generated by Django 4.0a1 on 2021-12-23 11:34

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0019_create_trigger"),
    ]

    operations = [
        migrations.AddField(
            model_name="tweet",
            name="bot_names",
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, default=[], null=True, size=None),
        ),
    ]
