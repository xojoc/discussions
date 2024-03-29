# Generated by Django 4.0a1 on 2022-10-04 18:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0054_alter_ad_topics"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ad",
            name="estimated_total_euro",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=19, null=True),
        ),
        migrations.AlterField(
            model_name="ad",
            name="floss_repository",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="ad",
            name="title",
            field=models.TextField(blank=True, null=True),
        ),
    ]
