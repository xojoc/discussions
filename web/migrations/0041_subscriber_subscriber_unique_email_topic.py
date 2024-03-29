# Generated by Django 4.0a1 on 2022-02-16 11:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0040_link_anchor_rel"),
    ]

    operations = [
        migrations.CreateModel(
            name="Subscriber",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("topic", models.CharField(choices=[("compsci", "Computer science"), ("devops", "DevOps"), ("rust", "Rust language")], max_length=255)),
                ("verification_code", models.CharField(max_length=15)),
                ("confirmed", models.BooleanField(default=False)),
                ("subscribed_from", models.CharField(choices=[("wf", "Web Form"), ("em", "Email Comand")], max_length=2, null=True)),
                ("entry_created_at", models.DateTimeField(auto_now_add=True)),
                ("entry_updated_at", models.DateTimeField(auto_now=True)),
                ("unsubscribed", models.BooleanField(default=False)),
                ("unsubscribed_at", models.DateTimeField(null=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="subscriber",
            constraint=models.UniqueConstraint(fields=("email", "topic"), name="unique_email_topic"),
        ),
    ]
