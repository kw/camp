# Generated by Django 4.2.10 on 2024-03-17 18:15

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0032_award_applied_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventreport",
            name="message",
            field=models.TextField(blank=True, default=None, null=True),
        ),
    ]