# Generated by Django 4.2.7 on 2024-02-09 21:49

import django.db.models.deletion
import rules.contrib.models
from django.conf import settings
from django.db import migrations
from django.db import models

import camp.game.models.event_models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("game", "0023_game_home_footer"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventReport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "report_type",
                    models.CharField(
                        help_text="Report type identifier, as used by the trigger-event-report view.",
                        max_length=50,
                    ),
                ),
                (
                    "task_id",
                    models.CharField(
                        default=camp.game.models.event_models._task_uuid,
                        help_text="Task ID used by the underlying task queue system.",
                        max_length=100,
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        blank=True,
                        default=None,
                        help_text="MIME type of the output, to report to the browser.",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "filename",
                    models.CharField(
                        blank=True,
                        default=None,
                        help_text="Filename to report to the browser. This is NOT a file on the webserver filesystem.",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "blob",
                    models.BinaryField(
                        default=None,
                        help_text="Report file content, once the task is complete.",
                        null=True,
                    ),
                ),
                (
                    "download_ready",
                    models.BooleanField(
                        default=False,
                        help_text="Marked True by the task once the report download is ready.",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="game.event",
                    ),
                ),
                (
                    "requestor",
                    models.ForeignKey(
                        blank=True,
                        help_text="The user who triggered the report.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="event_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
    ]
