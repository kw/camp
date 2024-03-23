# Generated by Django 4.2.11 on 2024-03-23 02:05

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0034_alter_eventreport_task_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="ruleset",
            name="remote_data",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Cached ruleset data, if it is successfully retrieved and validated.",
            ),
        ),
        migrations.AddField(
            model_name="ruleset",
            name="remote_error",
            field=models.TextField(
                blank=True,
                default="",
                help_text="If the last attempt to retrieve and validate remote data failed, the error message.",
            ),
        ),
        migrations.AddField(
            model_name="ruleset",
            name="remote_last_attempt",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="Last time an attempt was made to retrieve remote data.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ruleset",
            name="remote_last_updated",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="Last time the remote data was successfully retrieved and validated.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ruleset",
            name="remote_ok",
            field=models.BooleanField(
                blank=True,
                default=None,
                help_text="Was the last attempt to retrieve and validate remote data successful?",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ruleset",
            name="remote_token",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Bearer token to provide in HTTP requests.",
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name="ruleset",
            name="remote_url",
            field=models.CharField(
                blank=True, default="", help_text="URL to load from.", max_length=500
            ),
        ),
        migrations.AlterField(
            model_name="ruleset",
            name="package",
            field=models.CharField(
                blank=True,
                help_text="Python package where ruleset data can be loaded from. If a remote is provided, this is used only until remote data is loaded successfully.",
                max_length=100,
                null=True,
            ),
        ),
    ]