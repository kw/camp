# Generated by Django 4.2.7 on 2024-02-02 15:01

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0018_alter_event_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="cabin_allowed",
            field=models.BooleanField(
                default=True, help_text="Allow players to register for cabin lodging."
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="tenting_allowed",
            field=models.BooleanField(
                default=True,
                help_text="Allow players to register for tent-based lodging.",
            ),
        ),
        migrations.AddField(
            model_name="eventregistration",
            name="lodging",
            field=models.IntegerField(
                choices=[(0, "No Lodging"), (1, "Tent Camping"), (2, "Cabin")],
                default=0,
                help_text="What lodgings do you need? Daygamers, pick No Lodging. NPCs typically get a cabin.",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="eventregistration",
            name="lodging_group",
            field=models.TextField(
                blank=True,
                help_text="If you wish to stay with a group or individual, indicate that here. For any other lodging concerns, use the Details field.",
            ),
        ),
        migrations.AlterField(
            model_name="eventregistration",
            name="attendance",
            field=models.IntegerField(
                choices=[(0, "Full Game"), (1, "Day Game")],
                default=0,
                help_text="How much of the event are you registering for?",
            ),
        ),
    ]