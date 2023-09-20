"""Rule predicates for use in game permissions.

These permissions are actually defined in models.py,
but for historical reasons other modules import them from here.
"""
from __future__ import annotations

import rules
from django.contrib.auth import get_user_model

User = get_user_model()

# Authorization rules for game models.
is_authenticated = rules.is_authenticated
always_allow = rules.always_allow
always_deny = rules.always_deny


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
        if isinstance(obj.owners, models.QuerySet):
            return obj.owners.contains(user)
        else:
            return user in obj.owners
    return False


def get_game(obj) -> models.Game | None:
    if isinstance(obj, models.Game):
        return obj
    elif hasattr(obj, "game"):
        return obj.game if isinstance(obj.game, models.Game) else None
    elif hasattr(obj, "chapter") and hasattr(obj.chapter, "game"):
        return obj.chapter.game if isinstance(obj.chapter.game, models.Game) else None


def get_chapter(obj) -> models.Chapter | None:
    if isinstance(obj, models.Chapter):
        return obj
    elif hasattr(obj, "chapter"):
        return obj.chapter if isinstance(obj.chapter, models.Chapter) else None


def get_game_role(user: User, obj) -> models.GameRole | None:
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
        roles = models.GameRole.objects.filter(game=game, user=user)
        if roles and (role := roles[0]):
            return role


def get_chapter_role(user: User, obj) -> models.ChapterRole | None:
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
        roles = models.ChapterRole.objects.filter(chapter=chapter, user=user)
        if roles and (role := roles[0]):
            return role


# This must be at the bottom of this file, otherwise it will have a
# circular import problem.
from . import models  # noqa: E402
