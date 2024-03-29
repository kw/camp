# Generated by Django 4.2.10 on 2024-03-01 18:04

import django.db.models.deletion
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("character", "0006_character_discarded_by_character_discarded_date"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("game", "0028_award"),
    ]

    operations = [
        migrations.AlterField(
            model_name="award",
            name="awarded_by",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="awards_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="award",
            name="character",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="character.character",
            ),
        ),
        migrations.AlterField(
            model_name="award",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name="award",
            name="player",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
