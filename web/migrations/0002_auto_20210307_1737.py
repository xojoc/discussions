# Generated by Django 3.1.7 on 2021-03-07 17:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='discussion',
            name='canonical_redirect_url',
            field=models.CharField(blank=True, default=None, max_length=100000, null=True),
        ),
        migrations.AlterField(
            model_name='discussion',
            name='canonical_story_url',
            field=models.CharField(blank=True, max_length=100000, null=True),
        ),
    ]