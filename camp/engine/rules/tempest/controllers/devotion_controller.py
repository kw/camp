from __future__ import annotations

from functools import cached_property
from typing import cast

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class DevotionController(feature_controller.FeatureController):
    definition: defs.DevotionPower
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
            return Decision(success=False, reason="No parent religion defined.")
        if parent.value <= 0:
            return Decision(
                success=False, reason=f"You must have {parent.display_name()}"
            )
        if self.level == "advanced":
            # Advanced religion powers require that you have taken all basic powers
            # for the same religion.
            powers: list[DevotionController] = cast(
                list[DevotionController], parent.children
            )
            for power in powers:
                if power.level == "basic" and power.value == 0:
                    return Decision(
                        success=False,
                        reason=f"You must have all Basic Religion powers for [{parent.display_name()}](../{parent.full_id})",
                    )
        return super().meets_requirements
