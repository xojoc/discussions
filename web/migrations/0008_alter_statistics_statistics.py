# Generated by Django 3.2.6 on 2021-08-31 19:00

import django.core.serializers.json
from django.db import migrations, models
import web.models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0007_alter_statistics_statistics'),
    ]

    operations = [
        migrations.AlterField(
            model_name='statistics',
            name='statistics',
            field=models.JSONField(decoder=web.models.StatisticsDecoder, encoder=django.core.serializers.json.DjangoJSONEncoder),
        ),
    ]
