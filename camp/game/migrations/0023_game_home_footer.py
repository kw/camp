# Generated by Django 4.2.7 on 2024-02-08 14:01

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0022_alter_eventregistration_details_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="home_footer",
            field=models.TextField(blank=True),
        ),
    ]