# Generated by Django 4.0a1 on 2021-10-17 15:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0012_alter_tweet_tweet_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='discussion',
            name='platform_id',
            field=models.CharField(max_length=255, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='discussion',
            name='score',
            field=models.IntegerField(default=0, null=True),
        ),
    ]
