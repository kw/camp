from django.contrib.sites.models import Site
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .models import Game


class HomePageTests(TestCase):
    def setUp(self):
        self.home_site = Site.objects.create(domain="www.camp.internal", name="Home")
        self.game1_site = Site.objects.create(
            domain="game1.camp.internal", name="Game 1"
        )
        self.game1 = Game.objects.create(
            site=self.game1_site,
            description="The first game, which is open.",
            is_open=True,
        )
        self.game2_site = Site.objects.create(
            domain="game2.camp.internal", name="Game 2"
        )
        self.game2 = Game.objects.create(
            site=self.game2_site,
            description="The second game, which is closed.",
            is_open=False,
        )
        self.url = reverse("home")

    def test_get_hub_home(self):
        """When the current site has no associated game, render the hub page."""
        with override_settings(SITE_ID=self.home_site.id):
            response = self.client.get(self.url)
        self.assertTemplateUsed(response, "game/hub_home.html")
        self.assertContains(response, "Games")
        self.assertContains(response, self.game1.site.name)
        # This game isn't open, so it does not appear in the list.
        self.assertNotContains(response, self.game2.site.name)

    def test_get_hub_home_no_games_open(self):
        """When no games are open, the hub displays a message."""
        self.game1.is_open = False
        self.game1.save()
        with override_settings(SITE_ID=self.home_site.id):
            response = self.client.get(self.url)
        self.assertTemplateUsed(response, "game/hub_home.html")
        self.assertContains(response, "Games")
        self.assertContains(response, "No games currently open.")
        self.assertNotContains(response, self.game1.site.name)
        self.assertNotContains(response, self.game2.site.name)

    def test_get_game(self):
        """When the current site has a game attached, render the game home page."""
        with override_settings(SITE_ID=self.game1_site.id):
            response = self.client.get(self.url)
        self.assertTemplateUsed(response, "game/game_home.html")
        self.assertContains(response, "Game 1")
        self.assertContains(response, self.game1.description)
