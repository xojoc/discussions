# Generated by Django 4.0a1 on 2022-10-04 17:36

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0052_customuser_rss_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='AD',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('topics', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, max_length=255), blank=True, null=True, size=None)),
                ('week_year', models.IntegerField()),
                ('week_week', models.IntegerField()),
                ('newsletter', models.BooleanField(default=True)),
                ('twitter', models.BooleanField(default=False)),
                ('mastodon', models.BooleanField(default=False)),
                ('floss_project', models.BooleanField(default=False)),
                ('floss_repository', models.TextField(null=True)),
                ('title', models.TextField()),
                ('body', models.TextField()),
                ('url', models.TextField()),
                ('estimated_total_euro', models.DecimalField(decimal_places=4, max_digits=19, null=True)),
                ('user', models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, to='web.customuser')),
            ],
        ),
    ]
