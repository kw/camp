# Generated by Django 4.2.7 on 2024-02-04 18:00

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0021_event_payment_details_alter_event_location"),
    ]

    operations = [
        migrations.AlterField(
            model_name="eventregistration",
            name="details",
            field=models.TextField(blank=True, verbose_name="Other Details"),
        ),
        migrations.AlterField(
            model_name="eventregistration",
            name="lodging_group",
            field=models.TextField(
                blank=True,
                help_text="If you wish to stay with a group or individual, indicate that here. For any other lodging concerns, use the Other Details field.",
            ),
        ),
    ]
