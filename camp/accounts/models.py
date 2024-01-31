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

    joined: int = models.TimeField(auto_now_add=True)
    nickname: str = models.CharField(blank=True, max_length=50, default="nickname")
    game: int = models.ForeignKey(
        game_models.Game, on_delete=models.CASCADE, related_name="game"
    )
    user: str = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user")

    def __str__(self):
        return self.nickname

    class Meta:
        rules_permissions = {
            "view": game_models.is_self,
            "change": game_models.is_self
            | game_models.is_owner
            | game_models.is_logistics,
            "delete": game_models.is_self
            | game_models.is_owner
            | game_models.is_logistics,
            "add": game_models.is_authenticated,
        }
