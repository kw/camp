"""Rule predicates for use in game permissions.

These permissions are actually defined in models.py,
but for historical reasons other modules import them from here.
"""
from __future__ import annotations

from .models import always_allow
from .models import always_deny
from .models import can_manage_chapter
from .models import can_manage_chapter_not_self
from .models import can_manage_game
from .models import has_any_role
from .models import is_authenticated
from .models import is_chapter_logistics
from .models import is_chapter_manager
from .models import is_chapter_owner
from .models import is_chapter_plot
from .models import is_chapter_tavernkeep
from .models import is_game_auditor
from .models import is_game_manager
from .models import is_game_owner
from .models import is_game_rules_staff
from .models import is_logistics
from .models import is_owner
from .models import is_plot
from .models import self

__all__ = [
    "is_authenticated",
    "always_allow",
    "always_deny",
    "has_any_role",
    "self",
    "is_owner",
    "is_game_owner",
    "is_game_manager",
    "can_manage_game",
    "is_game_auditor",
    "is_game_rules_staff",
    "is_chapter_owner",
    "is_chapter_manager",
    "can_manage_chapter",
    "can_manage_chapter_not_self",
    "is_chapter_plot",
    "is_chapter_logistics",
    "is_chapter_tavernkeep",
    "is_logistics",
    "is_plot",
    "is_owner",
]
