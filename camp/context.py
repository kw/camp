from django.conf import settings as _settings
from django.http import HttpRequest


def settings(request):
    return {
        "site_title": _settings.SITE_TITLE,
    }


def game(request: HttpRequest):
    if request.site and hasattr(request.site, "game"):
        game = request.site.game
        if request.user.is_authenticated:
            is_owner = game.owners.contains(request.user)
        else:
            is_owner = False
        return {"game": game, "is_owner": is_owner}
    return {"game": None, "is_owner": False}


class CurrentGameMiddleware:
    """Assigns request.game to be the game associated with the site.

    If there is no game (this is the Game Hub), request.game = None.

    Must be installed after CurrentSiteMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if hasattr(request.site, "game"):
            request.game = request.site.game
        else:
            request.game = None
        return self.get_response(request)
