# Generated by Django 4.0a1 on 2021-10-09 17:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0009_tweet'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='discussion',
            index=models.Index(fields=['created_at'], name='web_discuss_created_9d621d_idx'),
        ),
    ]
