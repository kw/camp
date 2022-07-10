# Generated by Django 4.0.5 on 2022-07-10 16:07

import django.db.models.deletion
import rules.contrib.models
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("game", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="owners",
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="game",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="Chapter",
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
                ("slug", models.SlugField()),
                ("name", models.CharField(max_length=50)),
                ("description", models.TextField(blank=True)),
                ("is_open", models.BooleanField(default=True)),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chapters",
                        to="game.game",
                    ),
                ),
                ("owners", models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("game", "slug")},
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name="GameRole",
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
                (
                    "title",
                    models.CharField(
                        help_text="Title to display for this user (GM, Customer Service, etc)",
                        max_length=50,
                    ),
                ),
                (
                    "manager",
                    models.BooleanField(
                        default=False,
                        help_text="Can grant roles, sets game details, and manages chapters.",
                    ),
                ),
                (
                    "auditor",
                    models.BooleanField(
                        default=False, help_text="Can view data in any chapter."
                    ),
                ),
                (
                    "rules_staff",
                    models.BooleanField(
                        default=False, help_text="Can create and modify rulesets."
                    ),
                ),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="roles",
                        to="game.game",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="game_roles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("game", "user")},
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name="ChapterRole",
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
                (
                    "title",
                    models.CharField(
                        help_text="Title to display for this user (GM, Customer Service, etc)",
                        max_length=50,
                    ),
                ),
                (
                    "manager",
                    models.BooleanField(
                        default=False,
                        help_text="Can grant roles at the chapter level and set chapter details.",
                    ),
                ),
                (
                    "logistics_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Can manage events, grant rewards, etc.",
                    ),
                ),
                (
                    "plot_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Can view characters, write plot notes, etc.",
                    ),
                ),
                (
                    "tavern_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Set event meal information, view meal choices, see food allergy data.",
                    ),
                ),
                (
                    "chapter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="roles",
                        to="game.chapter",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chapter_roles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("chapter", "user")},
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
    ]
