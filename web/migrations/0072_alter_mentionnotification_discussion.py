# Generated by Django 4.0.8 on 2022-10-08 01:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0071_mention_keyword"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mentionnotification",
            name="discussion",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="web.discussion"),
        ),
    ]
