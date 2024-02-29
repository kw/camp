from django.apps import AppConfig
from django.db.models.signals import post_migrate

from .management.utils import create_default_game


class GameConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "camp.game"

    def ready(self):
        # Ensure a game is created by default at initial migration time.
        post_migrate.connect(create_default_game, sender=self)
