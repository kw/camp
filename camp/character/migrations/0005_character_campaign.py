# Generated by Django 4.2.7 on 2024-01-28 19:47

import django.db.models.deletion
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0011_alter_eventregistration_event"),
        ("character", "0004_undostackentry"),
    ]

    operations = [
        migrations.AddField(
            model_name="character",
            name="campaign",
            field=models.ForeignKey(
                blank=True,
                help_text="The campaign this character belongs to.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="characters",
                to="game.campaign",
            ),
        ),
    ]