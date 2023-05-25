from django.contrib.auth import get_user_model
from django.db import models
from game.models import Game

User = get_user_model()


class Membership(models.Model):
    """Represents a user's relationship with a game.

    A user can be a member of one or more games.
    For certain fields, a user gives a particular game only what
    information they want, so each game membership has its own data,
    though later we might add a feature to copy data between a user's
    memberships or otherwise keep them in sync.
    """

    joined: int = models.TimeField(auto_now_add=True)
    nickname: str = models.CharField(blank=True, max_length=50, default="nickname")
    game: int = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="game")
    user: User = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user")
