# Generated by Django 4.0a1 on 2021-12-29 12:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0025_resource_status_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='Link',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('anchor_title', models.TextField()),
            ],
        ),
        migrations.AddField(
            model_name='resource',
            name='links',
            field=models.ManyToManyField(related_name='link', through='web.Link', to='web.Resource'),
        ),
        migrations.AddField(
            model_name='link',
            name='from_resource',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='from_resource', to='web.resource'),
        ),
        migrations.AddField(
            model_name='link',
            name='to_resource',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='to_resource', to='web.resource'),
        ),
    ]