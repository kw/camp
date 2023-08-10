from __future__ import annotations

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class UtilityController(feature_controller.FeatureController):
    definition: defs.Utility

    def _utilities_available(self) -> int:
        if self.parent and self.parent.feature_type == "class":
            purchased = self.parent.utilities_purchased()
            utilties = self.character.get(f"{self.parent.full_id}.utilities")
            return utilties - purchased
        return 0

    def can_afford(self, value: int = 1) -> Decision:
        if self._utilities_available() >= value:
            return Decision.OK
        elif self.parent:
            return Decision(
                success=False,
                reason=f"Already purchased max {self.parent.display_name()} utilities",
            )
        else:
            return Decision(success=False)

    def explain_category_group(self) -> str | None:
        return f"{self._utilities_available()} {self.category} available"
