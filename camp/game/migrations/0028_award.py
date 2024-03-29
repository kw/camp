# Generated by Django 4.2.10 on 2024-02-28 23:34

import django.db.models.deletion
import rules.contrib.models
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("character", "0006_character_discarded_by_character_discarded_date"),
        ("game", "0027_eventregistration_award_applied_by_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Award",
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
                ("email", models.EmailField(max_length=254, null=True)),
                ("award_data", models.JSONField()),
                ("created_date", models.DateTimeField(auto_now_add=True)),
                (
                    "awarded_by",
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="awards_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="game.campaign"
                    ),
                ),
                (
                    "chapter",
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="game.chapter",
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="character.character",
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
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
