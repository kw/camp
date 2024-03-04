# Generated by Django 4.2.10 on 2024-03-02 22:09

import django.db.models.deletion
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0029_alter_award_awarded_by_alter_award_character_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="award",
            name="event",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="game.event",
            ),
        ),
    ]