from __future__ import annotations

import datetime

from django.contrib.auth import get_user_model
from django.db import models
from rules.contrib.models import RulesModel

from camp.game.models import game_models

User = get_user_model()


class Membership(RulesModel):
    """Represents a user's relationship with a game.

    A user can be a member of one or more games.
    For certain fields, a user gives a particular game only what
    information they want, so each game membership has its own data,
    though later we might add a feature to copy data between a user's
    memberships or otherwise keep them in sync.
    """

    game: int = models.ForeignKey(
        game_models.Game, on_delete=models.CASCADE, related_name="game"
    )
    user: str = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user")

    # Profile data tied to the membership.
    legal_name: str = models.CharField(
        max_length=100, help_text="Your legal name, for legal reasons."
    )
    preferred_name: str = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Name you prefer to use. We'll use it whenever possible.",
    )
    pronouns: str = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="What are your pronouns? Optional.",
    )
    birthdate: datetime.date = models.DateField(
        help_text="Your date of birth. Games have special rules regarding minors."
    )
    medical: str = models.TextField(
        blank=True,
        default="",
        help_text="Do you have any allergies or other medical conditions that you would like staff to know about?",
    )
    emergency_contacts: str = models.TextField(
        blank=True,
        default="",
        help_text="Please provide one or more emergency contacts.",
    )
    my_guardian: str = models.TextField(
        blank=True,
        default="",
        help_text="If you are a minor or otherwise require a guardian, who will serve as your guardian at games?",
    )
    my_minors: str = models.TextField(
        blank=True,
        default="",
        help_text="If you are a guardian for a minor you are responsible for at game, identify them here.",
    )

    @property
    def age(self) -> int:
        return (datetime.date.today() - self.birthdate).days // 365

    @classmethod
    def find(cls, request, user=None) -> Membership | None:
        return cls.objects.filter(
            game=request.game,
            user=user or request.user,
        ).first()

    def __str__(self):
        return (
            self.preferred_name
            or self.legal_name
            or self.user.get_full_name()
            or self.user.username
        )

    class Meta:
        rules_permissions = {
            "view": game_models.is_object_owner | game_models.is_logistics,
            "change": game_models.is_object_owner | game_models.is_logistics,
            "delete": game_models.is_object_owner | game_models.is_logistics,
        }
