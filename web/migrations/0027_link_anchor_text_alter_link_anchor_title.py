# Generated by Django 4.0a1 on 2021-12-29 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0026_link_resource_links_link_from_resource_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="link",
            name="anchor_text",
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name="link",
            name="anchor_title",
            field=models.TextField(null=True),
        ),
    ]
