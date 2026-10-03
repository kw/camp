from __future__ import annotations

from functools import cached_property

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class RoleController(feature_controller.FeatureController):
    definition: defs.Role
    supports_child_purchases: bool = True
    currency: str = "cp"

    def level_label(self) -> str:
        powers = [
            p
            for p in self.children
            if isinstance(p, RolePowerController) and p.level_value > 0
        ]
        powers.sort(key=lambda p: p.level_value)
        taken = [p for p in powers if p.value > 0]
        if len(powers) == len(taken):
            return "MAX"
        if taken:
            match taken[-1].level_value:
                case 2:
                    return "Advanced"
                case 1:
                    return "Basic"
        return ""


class RolePowerController(feature_controller.FeatureController):
    parent: RoleController
    definition: defs.RolePower
    currency: str = "cp"

    @cached_property
    def tags(self) -> set[str]:
        return super().tags | {self.level}

    @property
    def level(self) -> str:
        return self.definition.level

    @property
    def level_value(self) -> int:
        if self.is_advanced:
            return 2
        elif self.is_basic:
            return 1
        return 0

    @property
    def is_basic(self) -> bool:
        return self.definition.level == "basic"

    @property
    def is_advanced(self) -> bool:
        return self.definition.level == "advanced"

    @property
    def meets_requirements(self) -> Decision:
        if not (parent := self.parent):
            return Decision(success=False, reason="No parent role defined.")
        if parent.value <= 0:
            return Decision(
                success=False, reason=f"You must have {parent.display_name()}"
            )
        if self.level == "advanced":
            # Advanced role powers require that you have taken all basic powers
            # for the same role.
            for power in (
                c for c in parent.children if isinstance(c, RolePowerController)
            ):
                if power.level == "basic" and power.value == 0:
                    return Decision(
                        success=False,
                        reason=f"You must have all Basic Role powers for [{parent.display_name()}](../{parent.full_id})",
                    )
        return super().meets_requirements
