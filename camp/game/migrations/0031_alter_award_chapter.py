# Generated by Django 4.2.10 on 2024-03-04 13:11

import django.db.models.deletion
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0030_award_event"),
    ]

    operations = [
        migrations.AlterField(
            model_name="award",
            name="chapter",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="game.chapter",
            ),
        ),
    ]