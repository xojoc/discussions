# Generated by Django 4.0a1 on 2022-09-30 22:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0049_customuser_stripe_customer_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='complete_name',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='generic_ads',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='customuser',
            name='job_ads',
            field=models.BooleanField(default=False),
        ),
    ]
