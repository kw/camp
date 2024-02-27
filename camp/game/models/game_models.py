from __future__ import annotations

import datetime
from functools import cached_property
from functools import lru_cache
from typing import Any
from typing import TypeAlias

import rules
from django.conf import settings as _settings
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from rules.contrib.models import RulesModel

import camp.engine.loader
import camp.engine.rules.base_engine
import camp.engine.rules.base_models
from camp.engine.rules.tempest import campaign
from camp.engine.rules.tempest.records import PlayerRecord
from camp.engine.rules.tempest.records import PlayerRecordAdapter

User: TypeAlias = get_user_model()  # type: ignore


def _this_year():
    return datetime.date.today().year


# Authorization rules for game models.
is_authenticated = rules.is_authenticated
always_allow = rules.always_allow
always_deny = rules.always_deny


# --- PERMISSIONS FOR MODELS ---

# These rules predicates are used both within this model file and elsewhere throughout
# the project. Note that, unfortunately, the word "rules" is heavily overloaded in this
# module. Rules refer to both the Python "rules" package (which processes model permissions)
# as well as game rules (which process larp characters). Maybe we should rename the game rules?


@rules.predicate
def has_any_role(user: User, obj) -> bool:
    """Does this user have any role object in the object's chapter or game?

    Note that this doesn't mean any role bits are set, just that the
    user has a ChapterRole or GameRole, and thus has some sort of
    displayable title.
    """
    return (
        get_chapter_role(user, obj) is not None or get_game_role(user, obj) is not None
    )


@rules.predicate
def is_self(user: User, obj) -> bool:
    """Matches if the object's user is this user."""
    if isinstance(obj, User):
        return user == obj
    return user == getattr(obj, "user", None)


# Game-level predicates


@rules.predicate
def is_game_owner(user: User, obj) -> bool:
    """Is the user in the game's owner list?"""
    if user.is_anonymous:
        return False
    if game := get_game(obj):
        return game.owners.contains(user)
    return False


@rules.predicate
def is_game_manager(user: User, obj) -> bool:
    """Does the user have Manager role in this game?"""
    if role := get_game_role(user, obj):
        return role.manager
    return False


can_manage_game = is_game_owner | is_game_manager


@rules.predicate
def is_game_auditor(user: User, obj) -> bool:
    """Does the user have the Auditor role in this game?"""
    if role := get_game_role(user, obj):
        return role.auditor
    return False


@rules.predicate
def is_game_rules_staff(user: User, obj) -> bool:
    """Does the user have the Rules Staff role in this game?"""
    if role := get_game_role(user, obj):
        return role.rules_staff
    return False


# Chapter-level predicates


@rules.predicate
def is_chapter_owner(user: User, obj) -> bool:
    """Is the user in the chapter's owner list?"""
    if user.is_anonymous:
        return False
    if chapter := get_chapter(obj):
        return chapter.owners.contains(user)
    return False


@rules.predicate
def is_chapter_manager(user: User, obj) -> bool:
    """Does the user have Manager role in this chapter?"""
    if role := get_chapter_role(user, obj):
        return role.manager
    return False


can_manage_chapter = is_chapter_owner | is_chapter_manager
can_manage_chapter_not_self = is_chapter_owner | (is_chapter_manager & ~is_self)


@rules.predicate
def is_chapter_plot(user: User, obj) -> bool:
    """Is this user a member of the chapter's plot staff?"""
    if role := get_chapter_role(user, obj):
        return role.plot_staff
    return False


@rules.predicate
def is_chapter_logistics(user: User, obj):
    """Is this user a member of the chapter's logistics staff?"""
    if role := get_chapter_role(user, obj):
        return role.logistics_staff
    return False


can_manage_events = can_manage_chapter | is_chapter_logistics


@rules.predicate
def is_chapter_tavernkeep(user: User, obj):
    """Is this user a member of the chapter's tavern staff?"""
    if role := get_chapter_role(user, obj):
        return role.tavern_staff
    return False


# Generic predicates


@rules.predicate
def is_logistics(user: User, obj):
    """For an object associated with a game, is this user a logistics staff member in any chapter in that game?"""
    game = get_game(obj)
    if game is None:
        return False
    return any(is_chapter_logistics(user, chapter) for chapter in game.chapters.all())


@rules.predicate
def is_plot(user: User, obj):
    """For an object associated with a game, is this user a plot staff member in any chapter in that game?"""
    game = get_game(obj)
    if game is None:
        return False
    return any(is_chapter_plot(user, chapter) for chapter in game.chapters.all())


@rules.predicate
def is_owner(user: User, obj):
    """Is this user an owner of the object?"""
    if user.is_anonymous:
        return False
    if hasattr(obj, "owner"):
        if user == obj.owner:
            return True
        # Fall through, the object could also have an owners list
    if hasattr(obj, "owners"):
        # The owners attribute could be a QuerySet or some other container
        if hasattr(obj.owners, "contains"):
            return obj.owners.contains(user)
        else:
            return user in obj.owners
    return False


def get_game(obj) -> Game | None:
    if isinstance(obj, Game):
        return obj
    elif hasattr(obj, "game"):
        return obj.game if isinstance(obj.game, Game) else None
    elif hasattr(obj, "chapter") and hasattr(obj.chapter, "game"):
        return obj.chapter.game if isinstance(obj.chapter.game, Game) else None


def get_chapter(obj) -> Chapter | None:
    if isinstance(obj, Chapter):
        return obj
    elif hasattr(obj, "chapter"):
        return obj.chapter if isinstance(obj.chapter, Chapter) else None


def get_game_role(user: User, obj) -> GameRole | None:
    """Attempts to return a relevant game role for the user.

    Arguments:
        user: The user whose role should be gotten.
        obj: An object that is related to a game in an obvious way.
            Typically, this means the object is:
            a) A Game.
            b) A Chapter.
            c) Related to a game via a "game" attribute.
            d) Related to a chapter via a "chapter" attribute.
    """
    if not user.is_authenticated:
        return None
    if game := get_game(obj):
        roles = GameRole.objects.filter(game=game, user=user)
        if roles and (role := roles[0]):
            return role


def get_chapter_role(user: User, obj) -> ChapterRole | None:
    """Attempts to return a relevant chapter role for the user.

    Arguments:
        user: The user whose role should be gotten.
        obj: An object that is related to a chapter in an obvious way.
            Typically, this means the object is:
            a) A Chapter.
            b) Related to a chapter via a "chapter" attribute.
    """
    if not user.is_authenticated:
        return None
    if chapter := get_chapter(obj):
        roles = ChapterRole.objects.filter(chapter=chapter, user=user)
        if roles and (role := roles[0]):
            return role


# --- END PERMISSIONS ---


@lru_cache
def load_ruleset(path: str) -> camp.engine.rules.base_models.BaseRuleset:
    return camp.engine.loader.load_ruleset(path, with_bad_defs=False)


class Game(RulesModel):
    """Represents a top-level game.

    A game can have as many chapters and campaigns as desired,
    and each can run events with different rulesets if needed.
    Each game is associated with a particular subdomain.
    """

    name: str = models.CharField(blank=False, max_length=100, default="Game")
    description: str = models.TextField(blank=True, default="")
    home_footer: str = models.TextField(blank=True, default="")
    is_open: bool = models.BooleanField(default=False)
    # If a user is set as a game owner, they are always considered to have
    # role admin privileges, even if the corresponding roles are
    # (accidentally or maliciously) removed, deleted, or changed by a staff
    # member normally in charge of role administration.
    # A game owner can abdicate or transfer their ownership, but they can't
    # unilaterally add or remove other owners.
    # Owners can't be banned from their own games.
    owners: set[User] = models.ManyToManyField(User)

    @property
    def open_chapters(self):
        return self.chapters.filter(is_open=True)

    def __str__(self) -> str:
        return self.name

    def role_title(self, user: User, prefix: bool = False) -> str | None:
        """Calculate a display title for a user wrt this game.

        If the user has an assigned role for the game, the title
        will be returned if set. Otherwise, if the user is an owner
        of the game, they will show as "Owner". This allows owners
        to override their title if desired by assigning a role based
        on what they actually do in the game other than own it.

        If prefix = True, the game name will be prefixed for display in
        scenarios where staff from multiple chapters or games will be displayed.
        """
        if (role := get_game_role(user, self)) and role.title:
            return f"{self} {role.title}" if prefix else role.title
        if self.owners.contains(user):
            return f"{self} Owner" if prefix else "Owner"

    def set_role(
        self,
        user: User,
        title: str | None = None,
        manager: bool = False,
        auditor: bool = False,
        rules_staff: bool = False,
    ) -> GameRole:
        """Sets game role permissions for the given user.

        This is primarily for use in testing or shell use.

        If the user has existing role permissions for this game, they will
        be replaced with those specified. Any unset/unspecified roles will
        be removed if already in place. If no roles are specified, the user's
        role is downgraded to a generic "Volunteer" status rather than being
        outright removed.

        Arguments:
            user: The user to grant permissions for.
            title: Title to grant the user for this game. If not specified,
                a default will be used based on the permissions granted.
            manager: Grants the Manager role if set (default title: GM).
                This allows broad access to the game and chapters.
            auditor: Grants the Auditor role if set (default title: Auditor).
                This allows broad *read only* access to the game and chapters.
            rules_staff: Grants the Rules Staff role if set.

        Returns:
            The role object created or modified.
        """
        if title is None:
            if manager:
                title = "GM"
            elif auditor:
                title = "Auditor"
            elif rules_staff:
                title = "Rules Staff"
            else:
                title = "Volunteer"
        role: GameRole
        role, _ = GameRole.objects.get_or_create(game=self, user=user)
        role.title = title
        role.manager = manager
        role.auditor = auditor
        role.rules_staff = rules_staff
        role.save()
        return role

    class Meta:
        rules_permissions = {
            "view": always_allow,
            "change": can_manage_game,
        }


class Ruleset(RulesModel):
    """Represents a ruleset within a game.

    A ruleset is a set of game data (a list of skills, classes, etc)
    that specifies a game engine to run it. Rulesets may come from
    directories, archives, python packages, etc. The game engine
    specified in the ruleset must be installed in the server at
    a high enough version number to support the ruleset.

    While a rules engine can theoretically load data from anywhere,
    we don't want users of the service to try loading arbitrary
    disk locations. We'll only support python package names to start
    with, and later add support for ruleset uploads.
    """

    game: Game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="rulesets"
    )
    package: str = models.CharField(blank=True, null=True, max_length=100)
    enabled: bool = models.BooleanField(default=True)

    @cached_property
    def ruleset(self) -> camp.engine.rules.base_models.BaseRuleset:
        if not self.package:
            raise ValueError(f"No package specified for ruleset {self.name}")
        # Package loading behavior is triggered by prefixing a package with a $ character.
        return load_ruleset(f"${self.package}")

    @cached_property
    def engine(self) -> camp.engine.rules.base_engine.Engine:
        return self.ruleset.engine

    @property
    def ruleset_id(self) -> str:
        return self.ruleset.id

    @property
    def name(self) -> str:
        return self.ruleset.name

    @property
    def version(self) -> str:
        return self.ruleset.version

    def __str__(self) -> str:
        try:
            ruleset = self.ruleset
        except Exception:
            ruleset = None
        if ruleset:
            return f"{ruleset.name} [{ruleset.id} {ruleset.version}]" + (
                " (disabled)" if not self.enabled else ""
            )
        return f"Unreadable Ruleset [{self.package}]"

    def __repr__(self) -> str:
        return f"Ruleset(package={self.package}, enabled={self.enabled})"

    class Meta:
        rules_permissions = {
            "change": can_manage_game | is_game_rules_staff,
            "view": always_allow,
            "delete": can_manage_game | is_game_rules_staff,
        }


class Chapter(RulesModel):
    """Represents a specific organization in a game.

    Network games with presence across multiple states usually have different
    owners, plot teams, logistics, and other concerns. A game owner has limited
    direct privileges within a chapter, but game owners can create, transfer, or
    close a chapter.

    If a game only has a single chapter, some UI may be simplified.
    """

    game: Game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="chapters"
    )
    slug: str = models.SlugField(unique=True)
    name: str = models.CharField(max_length=50)
    description: str = models.TextField(blank=True, default="")
    is_open: bool = models.BooleanField(default=True)
    owners: set[User] = models.ManyToManyField(_settings.AUTH_USER_MODEL)
    timezone: str = models.CharField(max_length=50, help_text="e.g. 'America/Denver'")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def role_title(self, user: User, prefix: bool = False) -> str | None:
        """Calculate a display title for a user wrt this chapter.

        If the user has an assigned role for the game, the title
        will be returned if set. Otherwise, if the user is an owner
        of the game, they will show as "Chapter Owner".
        This allows owners to override their title if desired by assigning
        a role based on what they actually do in the game other than own it.

        If prefix = True, the chapter name will be prefixed for display in
        scenarios where staff from multiple chapters or games will be displayed.

        If the user has no chapter role but does have a role in the game,
        their prefixed game role title will be returned instead.
        """
        if (role := get_chapter_role(user, self)) and role.title:
            return f"{self} {role.title}" if prefix else role.title
        if self.owners.contains(user):
            return f"{self} Chapter Owner" if prefix else "Chapter Owner"
        return self.game.role_title(user, prefix=True)

    def set_role(
        self,
        user,
        title: str | None = None,
        manager: bool = False,
        logistics_staff: bool = False,
        plot_staff: bool = False,
        tavern_staff: bool = False,
    ) -> ChapterRole:
        """Sets chapter role permissions for the given user.

        This is primarily for use in testing or shell use.

        If the user has existing role permissions for this chapter, they will
        be replaced with those specified. Any unset/unspecified roles will
        be removed if already in place. If no roles are specified, the user's
        role is downgraded to a generic "Volunteer" status rather than being
        outright removed.

        Arguments:
            user: The user to grant permissions for.
            title: Title to grant the user for this game. If not specified,
                a default will be used based on the permissions granted.
            manager: Grants the Manager role if set (default title: GM).
                This allows broad access to the game and chapters.
            logistics_staff: Grants Logistics Staff role if set.
            plot_staff: Grants Plot Staff role if set.
            tavern_staff: Grants Tavern Staff role if set.

        Returns:
            The role object created or modified.
        """
        if title is None:
            if manager:
                title = "GM"
            elif logistics_staff:
                title = "Logistics"
            elif plot_staff:
                title = "Plot"
            elif tavern_staff:
                title = "Tavernkeep"
            else:
                title = "Volunteer"
        role: ChapterRole
        role, _ = ChapterRole.objects.get_or_create(chapter=self, user=user)
        role.title = title
        role.manager = manager
        role.logistics_staff = logistics_staff
        role.plot_staff = plot_staff
        role.tavern_staff = tavern_staff
        role.save()
        return role

    def get_absolute_url(self):
        return reverse("chapter-detail", kwargs={"slug": self.slug})

    class Meta:
        rules_permissions = {
            "view": always_allow,
            "add": can_manage_chapter | can_manage_game,
            "change": can_manage_chapter | can_manage_game,
        }


class Campaign(RulesModel):
    game: Game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="campaigns",
    )
    slug: str = models.SlugField(unique=True)
    name: str = models.CharField(blank=True, max_length=100, default="Campaign")
    start_year = models.IntegerField(default=_this_year)
    description: str = models.TextField(blank=True, default="")
    is_open: bool = models.BooleanField(default=False)
    ruleset: Ruleset = models.ForeignKey(
        Ruleset, null=True, on_delete=models.PROTECT, related_name="campaigns"
    )
    engine_data: dict[str, Any] = models.JSONField(null=True, blank=True, default=None)

    @property
    def record(self) -> campaign.CampaignRecord:
        if self.engine_data:
            model = campaign.CampaignAdapter.validate_python(self.engine_data)
            if model.name != self.name or model.start_year != self.start_year:
                model = model.model_copy(
                    update={"name": self.name, "start_year": self.start_year},
                )
            return model
        return campaign.CampaignRecord(
            name=self.name,
            start_year=self.start_year,
        )

    @record.setter
    def record(self, model: campaign.CampaignRecord):
        self.engine_data = model.model_dump(mode="json")

    def __str__(self) -> str:
        if self.name:
            return self.name
        return "Untitled Campaign"

    rules_permissions = {
        "add": can_manage_game,
        "change": can_manage_game,
        "view": can_manage_game,
    }


class GameRole(RulesModel):
    """Game-level roles for network admins and staff."""

    game: Game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="roles",
    )
    user: User = models.ForeignKey(
        _settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_roles",
    )
    title: str = models.CharField(
        max_length=50,
        help_text="Title to display for this user (GM, Customer Service, etc)",
    )

    manager: bool = models.BooleanField(
        default=False,
        help_text="Can grant roles, sets game details, and manages chapters.",
    )
    auditor: bool = models.BooleanField(
        default=False, help_text="Can view data in any chapter."
    )
    rules_staff: bool = models.BooleanField(
        default=False, help_text="Can create and modify rulesets."
    )

    def __str__(self):
        return f"{self.user} ({self.game} {self.title})"

    class Meta:
        unique_together = [["game", "user"]]
        rules_permissions = {
            "add": can_manage_game,
            "change": can_manage_game,
            "view": can_manage_game,
            "delete": can_manage_game,
        }


class ChapterRole(RulesModel):
    """Chapter-level roles for game runners, plot, logistics, etc."""

    chapter: Chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="roles",
    )
    user: User = models.ForeignKey(
        _settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chapter_roles",
    )
    title: str = models.CharField(
        max_length=50,
        help_text="Title to display for this user (GM, Customer Service, etc)",
    )

    manager: bool = models.BooleanField(
        default=False,
        help_text="Can grant roles at the chapter level and set chapter details.",
    )
    logistics_staff: bool = models.BooleanField(
        default=False, help_text="Can manage events, grant rewards, etc."
    )
    plot_staff: bool = models.BooleanField(
        default=False, help_text="Can view characters, write plot notes, etc."
    )
    tavern_staff: bool = models.BooleanField(
        default=False,
        help_text="Set event meal information, view meal choices, see food allergy data.",
    )

    def __str__(self):
        return f"{self.user} ({self.chapter} {self.title})"

    class Meta:
        unique_together = [["chapter", "user"]]
        rules_permissions = {
            "add": can_manage_chapter,
            "change": can_manage_chapter,
            "view": can_manage_chapter | can_manage_game,
            "delete": can_manage_chapter,
        }


class PlayerCampaignData(RulesModel):
    user = models.ForeignKey(
        _settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="player_data",
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="player_data",
    )
    data = models.JSONField(default=None, null=True, blank=True)

    @property
    def record(self) -> PlayerRecord:
        if self.data is None:
            return PlayerRecord(
                user=self.user_id,
            )
        return PlayerRecordAdapter.validate_python(self.data)

    @record.setter
    def record(self, value: PlayerRecord):
        self.data = value.model_dump(mode="json")

    @classmethod
    def retrieve_model(
        cls, user: User, campaign: Campaign, update: bool = True
    ) -> PlayerCampaignData:
        model, _ = cls.objects.get_or_create(user=user, campaign=campaign)
        campaign_record = campaign.record
        player_record = model.record
        if update:
            new_player_record = player_record.update(campaign_record)
            if new_player_record != player_record:
                model.record = new_player_record
        return model

    def __str__(self):
        return f"PlayerData({self.user}, {self.campaign})"

    class Meta:
        unique_together = [["user", "campaign"]]
