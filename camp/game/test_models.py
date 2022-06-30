from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import TestCase

from .models import Chapter
from .models import ChapterRole
from .models import Game
from .models import GameRole

VIEW_GAME = "game.view_game"
CHANGE_GAME = "game.change_game"
DELETE_GAME = "game.delete_game"
ADD_GAME = "game.add_game"

VIEW_CHAPTER = "game.view_chapter"
CHANGE_CHAPTER = "game.change_chapter"
DELETE_CHAPTER = "game.delete_chapter"
ADD_CHAPTER = "game.add_chapter"

VIEW_GAME_ROLE = "game.view_gamerole"
CHANGE_GAME_ROLE = "game.change_gamerole"
DELETE_GAME_ROLE = "game.delete_gamerole"
ADD_GAME_ROLE = "game.add_gamerole"

VIEW_CHAPTER_ROLE = "game.view_chapterrole"
CHANGE_CHAPTER_ROLE = "game.change_chapterrole"
DELETE_CHAPTER_ROLE = "game.delete_chapterrole"
ADD_CHAPTER_ROLE = "game.add_chapterrole"


class GamePermissionsTest(TestCase):
    """Checks that user.has_perm works as expected when game roles are in various states."""

    def setUp(self):
        self.owner: User = User.objects.create_user("owner")
        self.manager: User = User.objects.create_user("manager")
        self.manager2: User = User.objects.create_user("manager2")
        self.volunteer: User = User.objects.create_user("volunteer")
        self.player: User = User.objects.create_user("player")

        self.game_site: Site = Site.objects.create(
            domain="game.camp.internal", name="Tempest"
        )
        self.other_site: Site = Site.objects.create(
            domain="other.camp.internal", name="Other Game"
        )
        self.game: Game = Game.objects.create(
            site=self.game_site,
            description="The first game",
            is_open=True,
        )
        self.game.owners.add(self.owner)

        self.other_game: Game = Game.objects.create(
            site=self.other_site,
            description="Some other game",
        )

        self.role: GameRole = self.game.set_role(self.manager, manager=True)
        self.game.set_role(self.manager2, manager=True)
        self.game.set_role(self.volunteer)

    def test_role_titles(self):
        """Titles are either derived from role permissions or explicitly set."""
        self.assertEqual("Owner", self.game.role_title(self.owner))
        self.assertEqual("Tempest Owner", self.game.role_title(self.owner, prefix=True))

        self.assertEqual("GM", self.game.role_title(self.manager))
        self.assertEqual("Tempest GM", self.game.role_title(self.manager, prefix=True))

        self.assertEqual("Volunteer", self.game.role_title(self.volunteer))

        self.assertIsNone(self.game.role_title(self.player))
        self.game.set_role(self.player, title="New Recruit")
        self.assertEqual("New Recruit", self.game.role_title(self.player))

    def test_anonymous_permissions(self):
        """Permissions related to anonymous users."""
        anon = AnonymousUser()
        self.assertTrue(
            anon.has_perm(VIEW_GAME, self.game),
            "Any user, including anonymous ones, can view games.",
        )
        self.assertFalse(
            anon.has_perm(CHANGE_GAME, self.game), "Anonymous users can't change games."
        )
        self.assertFalse(
            anon.has_perm(DELETE_GAME, self.game), "Anonymous users can't delete games."
        )
        self.assertFalse(
            anon.has_perm(ADD_GAME, self.game), "Anonymous user can't create games."
        )

    def test_owner_permissions(self):
        """Permissions related to game owners."""
        self.assertTrue(
            self.owner.has_perm(VIEW_GAME, self.game), "Owners can view games."
        )
        self.assertTrue(
            self.owner.has_perm(CHANGE_GAME, self.game),
            "Owners can change their own games.",
        )
        self.assertFalse(
            self.owner.has_perm(DELETE_GAME, self.game),
            "Owners can't delete games (only archive them).",
        )
        self.assertFalse(
            self.owner.has_perm(CHANGE_GAME, self.other_game),
            "Owners can't change games they don't own",
        )
        self.assertFalse(
            self.owner.has_perm(ADD_GAME, self.game),
            "Users can't sneakily try to create a game that they own somehow",
        )
        self.assertFalse(
            self.owner.has_perm(ADD_GAME, self.other_game),
            "Users that own a game can't create some other game",
        )

    def test_manager_permissions(self):
        """Permissions related to game managers."""
        self.assertTrue(
            self.manager.has_perm(VIEW_GAME, self.game), "Managers can view games."
        )
        self.assertTrue(
            self.manager.has_perm(CHANGE_GAME, self.game),
            "Managers can change their own games.",
        )
        self.assertFalse(
            self.manager.has_perm(DELETE_GAME, self.game),
            "Managers can't delete games.",
        )
        self.assertFalse(
            self.manager.has_perm(CHANGE_GAME, self.other_game),
            "Managers can't change games they don't manage",
        )
        self.assertFalse(
            self.manager.has_perm(ADD_GAME, self.game), "Managers can't create a game"
        )

    def test_player_permissions(self):
        """Permissions related to players (no GameRole)."""
        self.assertTrue(
            self.player.has_perm(VIEW_GAME, self.game), "Players can view games"
        )
        self.assertFalse(
            self.player.has_perm(CHANGE_GAME, self.game), "Players can't change games."
        )
        self.assertFalse(
            self.player.has_perm(DELETE_GAME, self.game), "Players can't delete games."
        )
        self.assertFalse(
            self.player.has_perm(ADD_GAME, self.game), "Players can't create games."
        )

    def test_volunteer_permissions(self):
        """Permissions for a user with a role, but no permissions."""
        self.assertTrue(
            self.volunteer.has_perm(VIEW_GAME, self.game),
            "Volunteer user can view games",
        )
        self.assertFalse(
            self.volunteer.has_perm(CHANGE_GAME, self.game),
            "Volunteer user can't change games.",
        )
        self.assertFalse(
            self.volunteer.has_perm(DELETE_GAME, self.game),
            "Volunteer user can't delete games.",
        )
        self.assertFalse(
            self.volunteer.has_perm(ADD_GAME, self.game),
            "Volunteers can't create games.",
        )

    def test_role_permissions(self):
        """Permissions for working with GameRoles themselves."""

        # Owners can do anything with a GameRole
        self.assertTrue(self.owner.has_perm(VIEW_GAME_ROLE, self.role))
        self.assertTrue(self.owner.has_perm(CHANGE_GAME_ROLE, self.role))
        self.assertTrue(self.owner.has_perm(DELETE_GAME_ROLE, self.role))
        self.assertTrue(self.owner.has_perm(ADD_GAME_ROLE, self.role))

        # Managers can generally also do anything with roles, but can't modify their own.
        # Exception: A manager can abdicate their role by deleting it.
        # Note here that self.role is the role for self.manager.
        self.assertTrue(self.manager.has_perm(VIEW_GAME_ROLE, self.role))
        self.assertFalse(self.manager.has_perm(CHANGE_GAME_ROLE, self.role))
        self.assertTrue(self.manager.has_perm(DELETE_GAME_ROLE, self.role))
        self.assertFalse(self.manager.has_perm(ADD_GAME_ROLE, self.role))

        # But a different manager _can_ add or change the role.
        self.assertTrue(self.manager2.has_perm(VIEW_GAME_ROLE, self.role))
        self.assertTrue(self.manager2.has_perm(CHANGE_GAME_ROLE, self.role))
        self.assertTrue(self.manager2.has_perm(DELETE_GAME_ROLE, self.role))
        self.assertTrue(self.manager2.has_perm(ADD_GAME_ROLE, self.role))

        # Others can't do anything with it.
        self.assertFalse(self.player.has_perm(VIEW_GAME_ROLE, self.role))
        self.assertFalse(self.player.has_perm(CHANGE_GAME_ROLE, self.role))
        self.assertFalse(self.player.has_perm(DELETE_GAME_ROLE, self.role))
        self.assertFalse(self.player.has_perm(ADD_GAME_ROLE, self.role))


class ChapterPermissionsTest(TestCase):
    """Checks that user.has_perm works as expected when chapter roles are in various states."""

    def setUp(self):
        self.game_owner: User = User.objects.create_user("game_owner")
        self.game_manager: User = User.objects.create_user("game_manager")

        self.chapter_owner: User = User.objects.create_user("chapter_owner")
        self.chapter_manager: User = User.objects.create_user("manager")
        self.volunteer: User = User.objects.create_user("volunteer")
        self.player: User = User.objects.create_user("player")

        self.game_site: Site = Site.objects.create(
            domain="game.camp.internal", name="Tempest"
        )
        self.other_site: Site = Site.objects.create(
            domain="other.camp.internal", name="Other"
        )
        self.game: Game = Game.objects.create(
            site=self.game_site,
            description="The first game",
            is_open=True,
        )
        self.game.owners.add(self.game_owner)

        self.other_game: Game = Game.objects.create(
            site=self.other_site,
            description="Some other game",
            is_open=True,
        )

        self.chapter: Chapter = Chapter.objects.create(
            game=self.game,
            name="Denver",
            slug="denver",
        )
        self.chapter.owners.add(self.chapter_owner)

        self.other_chapter: Chapter = Chapter.objects.create(
            game=self.game,
            name="Kansas",
            slug="kansas",
        )

        self.other_game_chapter: Chapter = Chapter.objects.create(
            game=self.other_game,
            name="Hawaii",
            slug="hawaii",
        )

        self.game.set_role(self.game_manager, manager=True)
        self.role: ChapterRole = self.chapter.set_role(
            self.chapter_manager, manager=True
        )
        self.chapter.set_role(self.volunteer)

    def test_role_titles(self):
        """Titles are either derived from role permissions or explicitly set."""
        self.assertEqual("Chapter Owner", self.chapter.role_title(self.chapter_owner))
        self.assertEqual(
            "Denver Chapter Owner",
            self.chapter.role_title(self.chapter_owner, prefix=True),
        )

        self.assertEqual("Tempest Owner", self.chapter.role_title(self.game_owner))

        self.assertEqual("GM", self.chapter.role_title(self.chapter_manager))
        self.assertEqual(
            "Denver GM", self.chapter.role_title(self.chapter_manager, prefix=True)
        )

        self.assertEqual("Volunteer", self.chapter.role_title(self.volunteer))

        self.assertIsNone(self.chapter.role_title(self.player))
        self.chapter.set_role(self.player, title="Player")
        self.assertEqual("Player", self.chapter.role_title(self.player))

    def test_anonymous_permissions(self):
        """Permissions related to anonymous users."""
        anon = AnonymousUser()
        self.assertTrue(
            anon.has_perm(VIEW_CHAPTER, self.chapter),
            "Any user, including anonymous ones, can view chapters.",
        )
        self.assertFalse(
            anon.has_perm(CHANGE_CHAPTER, self.chapter),
            "Anonymous users can't change chapters.",
        )
        self.assertFalse(
            anon.has_perm(DELETE_CHAPTER, self.chapter),
            "Anonymous users can't delete chapters.",
        )
        self.assertFalse(
            anon.has_perm(ADD_CHAPTER, self.chapter),
            "Anonymous users can't add chapters.",
        )

    def test_owner_permissions(self):
        """Permissions related to chapter owners."""
        self.assertTrue(
            self.chapter_owner.has_perm(VIEW_CHAPTER, self.chapter),
            "Owners can view chapters.",
        )
        self.assertTrue(
            self.chapter_owner.has_perm(CHANGE_CHAPTER, self.chapter),
            "Owners can change their own chapters.",
        )
        self.assertFalse(
            self.chapter_owner.has_perm(DELETE_CHAPTER, self.chapter),
            "Owners can't delete chapters (only archive them).",
        )
        self.assertFalse(
            self.chapter_owner.has_perm(CHANGE_CHAPTER, self.other_chapter),
            "Owners can't change chapters they don't own",
        )
        self.assertFalse(
            self.chapter_owner.has_perm(ADD_CHAPTER, self.chapter),
            "Users can't add chapters that they somehow own.",
        )
        self.assertFalse(
            self.chapter_owner.has_perm(ADD_CHAPTER, self.other_chapter),
            "Users can't add chapters that they don't own either.",
        )

    def test_game_manager_permissions(self):
        """Permissions related to game managers."""
        self.assertTrue(
            self.game_manager.has_perm(VIEW_CHAPTER, self.chapter),
            "Game managers can view chapters.",
        )
        self.assertTrue(
            self.game_manager.has_perm(CHANGE_CHAPTER, self.chapter),
            "Game managers can change chapters in their games.",
        )
        self.assertFalse(
            self.game_manager.has_perm(DELETE_CHAPTER, self.chapter),
            "Game managers can't delete chapters (only archive them).",
        )
        self.assertFalse(
            self.game_manager.has_perm(CHANGE_CHAPTER, self.other_game_chapter),
            "Game managers can't change chapters in games they don't manage.",
        )
        self.assertTrue(
            self.game_manager.has_perm(ADD_CHAPTER, self.chapter),
            "Game managers can add new chapters.",
        )

    def test_chapter_manager_permissions(self):
        """Permissions related to chapter managers."""
        self.assertTrue(
            self.chapter_manager.has_perm(VIEW_CHAPTER, self.chapter),
            "Chapter managers can view chapters.",
        )
        self.assertTrue(
            self.chapter_manager.has_perm(CHANGE_CHAPTER, self.chapter),
            "Chapter managers can change their own chapters.",
        )
        self.assertFalse(
            self.chapter_manager.has_perm(DELETE_CHAPTER, self.chapter),
            "Chapter managers can't delete chapters.",
        )
        self.assertFalse(
            self.chapter_manager.has_perm(CHANGE_CHAPTER, self.other_chapter),
            "Chapter managers can't change chapters they don't manage",
        )
        self.assertFalse(
            self.chapter_manager.has_perm(ADD_CHAPTER, self.chapter),
            "Chapter managers can't add new chapters",
        )

    def test_player_permissions(self):
        """Permissions related to players (no ChapterRole)."""
        self.assertTrue(
            self.player.has_perm(VIEW_CHAPTER, self.chapter),
            "Players can view chapters",
        )
        self.assertFalse(
            self.player.has_perm(CHANGE_CHAPTER, self.chapter),
            "Players can't change chapters.",
        )
        self.assertFalse(
            self.player.has_perm(DELETE_CHAPTER, self.chapter),
            "Players can't delete chapters.",
        )
        self.assertFalse(
            self.player.has_perm(ADD_CHAPTER, self.chapter),
            "Players can't create chapters.",
        )

    def test_volunteer_permissions(self):
        """Permissions for a user with a role, but no permissions."""
        self.assertTrue(
            self.volunteer.has_perm(VIEW_CHAPTER, self.chapter),
            "Volunteer can view chapters",
        )
        self.assertFalse(
            self.volunteer.has_perm(CHANGE_CHAPTER, self.chapter),
            "Volunteer can't change chapters.",
        )
        self.assertFalse(
            self.volunteer.has_perm(DELETE_CHAPTER, self.chapter),
            "Volunteer can't delete chapters.",
        )
        self.assertFalse(
            self.volunteer.has_perm(ADD_CHAPTER, self.chapter),
            "Volunteers can't add chapters.",
        )

    def test_role_permissions(self):
        """Permissions for working with ChapterRoles themselves."""

        # Owners can do anything with a ChapterRole
        self.assertTrue(self.chapter_owner.has_perm(VIEW_CHAPTER_ROLE, self.role))
        self.assertTrue(self.chapter_owner.has_perm(CHANGE_CHAPTER_ROLE, self.role))
        self.assertTrue(self.chapter_owner.has_perm(DELETE_CHAPTER_ROLE, self.role))
        self.assertTrue(self.chapter_owner.has_perm(ADD_CHAPTER_ROLE, self.role))

        # Managers can generally also do anything with roles, but can't modify their own.
        # Exception: A manager can abdicate their role by deleting it.
        # Note here that self.role is the role for self.manager.
        self.assertTrue(self.chapter_manager.has_perm(VIEW_CHAPTER_ROLE, self.role))
        self.assertFalse(self.chapter_manager.has_perm(CHANGE_CHAPTER_ROLE, self.role))
        self.assertTrue(self.chapter_manager.has_perm(DELETE_CHAPTER_ROLE, self.role))
        self.assertFalse(self.chapter_manager.has_perm(ADD_CHAPTER_ROLE, self.role))

        # Just because you're a game manager doesn't mean you get to much around in
        # chapter roles, but you can at least _see_ them.
        self.assertTrue(self.game_manager.has_perm(VIEW_CHAPTER_ROLE, self.role))
        self.assertFalse(self.game_manager.has_perm(CHANGE_CHAPTER_ROLE, self.role))
        self.assertFalse(self.game_manager.has_perm(DELETE_CHAPTER_ROLE, self.role))
        self.assertFalse(self.game_manager.has_perm(ADD_CHAPTER_ROLE, self.role))

        # Others can't do anything with it.
        self.assertFalse(self.player.has_perm(VIEW_CHAPTER_ROLE, self.role))
        self.assertFalse(self.player.has_perm(CHANGE_CHAPTER_ROLE, self.role))
        self.assertFalse(self.player.has_perm(DELETE_CHAPTER_ROLE, self.role))
        self.assertFalse(self.player.has_perm(ADD_CHAPTER_ROLE, self.role))
