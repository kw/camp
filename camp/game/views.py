from django.views.generic import ListView

from .models import Game
from .models import GameRole


class HomePageView(ListView):
    def is_game(self):
        return self.request.site and hasattr(self.request.site, "game")

    def get_queryset(self, **kwargs):
        if self.is_game():
            # TODO: We'll probably want to list something on the game home.
            return Game.objects.none()
        else:
            return Game.objects.filter(is_open=True)

    def get_template_names(self):
        if self.is_game():
            return ["game/game_home.html"]
        else:
            return ["game/hub_home.html"]


class GameRolesListView(ListView):
    model = GameRole

    def get_queryset(self):
        return GameRole.objects.filter(game=self.request.site.game)
