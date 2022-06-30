from __future__ import annotations

from django.conf import settings as _settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.db import models
from django.utils.text import slugify
from rules.contrib.models import RulesModel

from . import rules

User = get_user_model()


class Game(RulesModel):
    """Represents a top-level game.

    A game can have as many chapters and campaigns as desired,
    and each can run events with different rulesets if needed.
    Each game is associated with a particular subdomain.
    """

    site: Site = models.OneToOneField(Site, on_delete=models.CASCADE)
    description: str = models.TextField(blank=True)
    is_open: bool = models.BooleanField(default=False)
    # If a user is set as a game owner, they are always considered to have
    # role admin privileges, even if the corresponding roles are
    # (accidentally or maliciously) removed, deleted, or changed by a staff
    # member normally in charge of role administration.
    # A game owner can abdicate or transfer their ownership, but they can't
    # unilaterally add or remove other owners.
    # Owners can't be banned from their own games.
    owners: set[User] = models.ManyToManyField(User)

    def __str__(self) -> str:
        return self.site.name

    def get_absolute_url(self, request=None) -> str:
        """Produces a fully-qualified URL.

        It's easier to fill in if a request is provided. Otherwise,
        we try to infer from settings.
        """
        if request:
            scheme = request.scheme
        elif _settings.HOST_PORT == "443" or not _settings.HOST_PORT:
            scheme = "https"
        else:
            scheme = "http"
        port_str = f":{_settings.HOST_PORT}" if _settings.HOST_PORT else ""
        return f"{scheme}://{self.site.domain}{port_str}/"

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
        if (role := rules.get_game_role(user, self)) and role.title:
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
            "view": rules.always_allow,
            "change": rules.can_manage_game,
        }


class Chapter(RulesModel):
    """Represents a specific organization in a game.

    Network games with presence across multiple states usually have different
    owners, plot teams, logistics, and other concerns. A game owner has limited
    direct privileges within a chapter, but game owners can create, transfer, or
    close a chapter.

    If a game only has a single chapter, some UI may be simplified.
    """

    game: Game = models.ForeignKey(Game, on_delete=models.CASCADE)
    slug: str = models.SlugField()
    name: str = models.CharField(max_length=50)
    description: str = models.TextField(blank=True)
    is_open: bool = models.BooleanField(default=True)
    owners: set[User] = models.ManyToManyField(_settings.AUTH_USER_MODEL)

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
        if (role := rules.get_chapter_role(user, self)) and role.title:
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

    class Meta:
        unique_together = [["game", "slug"]]
        rules_permissions = {
            "add": rules.can_manage_game,
            "view": rules.always_allow,
            "change": rules.can_manage_chapter | rules.can_manage_game,
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
            "add": rules.can_manage_game_not_self,
            "change": rules.can_manage_game_not_self,
            "view": rules.can_manage_game,
            "delete": rules.can_manage_game,
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
            "add": rules.can_manage_chapter_not_self,
            "change": rules.can_manage_chapter_not_self,
            "view": rules.can_manage_chapter | rules.can_manage_game,
            "delete": rules.can_manage_chapter,
        }
