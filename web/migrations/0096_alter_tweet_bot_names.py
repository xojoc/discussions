# Generated by Django 4.2.6 on 2023-10-19 20:50

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0095_databag'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tweet',
            name='bot_names',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, default=list, size=None),
        ),
    ]