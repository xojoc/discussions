# Generated by Django 4.2.6 on 2023-10-22 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0098_remove_discussion_category_discussion__category'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='databag',
            name='id',
        ),
        migrations.AlterField(
            model_name='databag',
            name='key',
            field=models.CharField(primary_key=True, serialize=False),
        ),
    ]
