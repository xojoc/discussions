# Generated by Django 4.1.7 on 2023-03-20 20:55

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("web", "0076_alter_resource_pagerank"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriber",
            name="suspected_spam",
            field=models.BooleanField(default=False),
        ),
    ]
