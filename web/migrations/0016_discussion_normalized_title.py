# Generated by Django 4.0a1 on 2021-12-16 13:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0015_discussion_normalized_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='discussion',
            name='normalized_title',
            field=models.CharField(blank=True, max_length=2048, null=True),
        ),
    ]
