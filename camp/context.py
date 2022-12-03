from django.apps import apps
from django.conf import settings as _settings
from django.http import HttpRequest


def settings(request):
    return {
        "site_title": _settings.SITE_TITLE,
    }


def game(request: HttpRequest):
    Game = apps.get_model("game", "Game")
    game = Game.objects.get(pk=_settings.GAME_ID)
    if hasattr(request, "user") and request.user.is_authenticated:
        is_owner = game.owners.contains(request.user)
    else:
        is_owner = False
    return {"game": game, "is_owner": is_owner}


class CurrentGameMiddleware:
    """Assigns request.game to be the game associated with the site."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        context = game(request)
        request.game = context["game"]
        request.is_owner = context["is_owner"]
        return self.get_response(request)
