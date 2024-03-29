# Generated by Django 4.0.8 on 2022-10-07 17:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0068_mentionnotification_email_sent_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mention",
            name="rule_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="mention",
            name="url_pattern",
            field=models.TextField(help_text="\nInsert a URL pattern without the protocol.<br/>\nUse % to represent any string.<br/>\nURLs are normalized so: https://discu.eu, http://www.discu.eu and https://mobile.discu.eu all match discu.eu/%<br/>\nExamples:\n<ul>\n    <li>discu.eu/%</li>\n    <li>twitter.com/xojoc/%</li>\n</ul>\n    "),
        ),
    ]
