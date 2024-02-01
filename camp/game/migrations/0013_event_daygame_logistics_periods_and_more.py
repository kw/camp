# Generated by Django 4.2.7 on 2024-01-31 23:07

from decimal import Decimal

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0012_alter_event_logistics_periods"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="daygame_logistics_periods",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("2"),
                help_text="How many long rests for a daygamer? Set to zero to disallow daygaming. Must be less than the normal reward.",
                max_digits=4,
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="registration_open",
            field=models.DateTimeField(
                blank=True,
                help_text="When should the Register button be shown, in the chapter's local timezone? Leave blank to never open (until you set it).",
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.CheckConstraint(
                check=models.Q(("logistics_periods__gte", Decimal("0"))),
                name="logistics_periods_nonneg",
                violation_error_message="Number of logistics periods must be non-negative.",
            ),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("daygame_logistics_periods__lte", models.F("logistics_periods"))
                ),
                name="daygame_reward",
                violation_error_message="Daygame logistics reward must not be greater than the normal one.",
            ),
        ),
    ]
