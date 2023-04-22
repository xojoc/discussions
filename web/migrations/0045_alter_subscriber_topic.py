# Generated by Django 4.0a1 on 2022-05-15 02:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0044_alter_subscriber_topic"),
    ]

    operations = [
        migrations.AlterField(
            model_name="subscriber",
            name="topic",
            field=models.CharField(choices=[("candcpp", "C & C++"), ("compsci", "Computer science"), ("devops", "DevOps"), ("erlang", "Erlang & Elixir"), ("golang", "Golang"), ("hackernews", "Hacker News"), ("haskell", "Haskell"), ("laarc", "Laarc"), ("lisp", "Lisp & Scheme"), ("programming", "Software Development"), ("python", "Python"), ("ruby", "Ruby"), ("rust", "Rust"), ("unix", "Unix")], max_length=255),
        ),
    ]
