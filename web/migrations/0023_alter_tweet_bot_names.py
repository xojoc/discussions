# Generated by Django 4.0a1 on 2021-12-26 21:35

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0022_update_trigger'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tweet',
            name='bot_names',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, default=list, null=True, size=None),
        ),
    ]
