# Generated by Django 4.1.3 on 2022-12-03 19:42

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0002_remove_game_site_game_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="game",
            name="name",
            field=models.CharField(default="Game", max_length=100),
        ),
    ]
