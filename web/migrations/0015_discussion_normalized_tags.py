# Generated by Django 4.0a1 on 2021-12-16 13:15

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0014_discussion_entry_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='discussion',
            name='normalized_tags',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, max_length=255), blank=True, null=True, size=None),
        ),
    ]