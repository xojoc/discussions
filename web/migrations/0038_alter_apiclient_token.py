# Generated by Django 4.0a1 on 2022-01-14 16:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0037_apiclient_email"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apiclient",
            name="token",
            field=models.TextField(null=True),
        ),
    ]
