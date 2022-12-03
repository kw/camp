from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from camp.game.models import Chapter
from camp.game.models import Game


class HomePageTests(TestCase):
    def setUp(self):
        self.game1 = Game.objects.create(
            name="Game 1",
            description="The first game, which is open.",
            is_open=True,
        )
        self.game2 = Game.objects.create(
            name="Game 2",
            description="The second game, which is closed.",
            is_open=False,
        )
        self.chapter1 = Chapter.objects.create(
            game=self.game1,
            slug="denver",
            name="Denver",
            is_open=True,
        )
        self.chapter2 = Chapter.objects.create(
            game=self.game1,
            slug="kansas",
            name="Kansas",
            is_open=False,
        )
        self.chapter3 = Chapter.objects.create(
            game=self.game2,
            slug="hawaii",
            name="Hawaii",
            is_open=True,
        )
        self.url = reverse("home")

    def test_get_game_one(self):
        """When the current site has a game attached, render the game home page."""
        with override_settings(GAME_ID=self.game1.id):
            response = self.client.get(self.url)
        self.assertTemplateUsed(response, "game/game_home.html")
        self.assertContains(response, "Game 1")
        self.assertContains(response, self.game1.description)
        # Only open chapters are listed.
        self.assertContains(response, "Denver")
        self.assertNotContains(response, "Kansas")

    def test_get_game_two(self):
        with override_settings(GAME_ID=self.game2.id):
            response = self.client.get(self.url)
        self.assertTemplateUsed(response, "game/game_home.html")
        self.assertContains(response, "Game 2")
        self.assertContains(response, self.game2.description)
        # Only open chapters are listed.
        self.assertNotContains(response, "Denver")
        self.assertContains(response, "Hawaii")
