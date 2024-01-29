"""Creates a default Game object linked to the default Site."""

from django.apps import apps as global_apps
from django.db import DEFAULT_DB_ALIAS
from django.db import router


def create_default_game(
    app_config,
    verbosity=2,
    interactive=True,
    using=DEFAULT_DB_ALIAS,
    apps=global_apps,
    **kwargs,
):
    try:
        Game = apps.get_model("game", "Game")
    except LookupError:
        return

    if not router.allow_migrate_model(using, Game):
        return

    if not Game.objects.using(using).exists():
        if verbosity >= 2:
            print("Creating default Game object")
        Game(id=1, description="The default game. Change me!", is_open=False).save(
            using=using
        )
