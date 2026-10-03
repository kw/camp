from __future__ import annotations

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class UtilityController(feature_controller.FeatureController):
    definition: defs.Utility

    def _utilities_available(self) -> int:
        if self.parent and self.parent.feature_type == "class":
            purchased = self.parent.utilities_purchased()
            utilties = self.parent.utilities_awarded()
            return utilties - purchased
        return 0

    def can_afford(self, value: int = 1) -> Decision:
        available = self._utilities_available()
        if available >= value:
            return Decision.OK
        elif self.parent:
            return Decision(
                success=False,
                reason=f"Already purchased max {self.parent.display_name()} utilities",
                available=max(available, 0),
            )
        else:
            return Decision(success=False)

    def explain_category_group(self) -> str | None:
        return f"{self._utilities_available()} {self.category} available"

    @property
    def explain_list(self) -> list[str]:
        explain = []
        for claz in self.character.classes:
            available = claz.utilities_awarded() - claz.utilities_purchased()
            if available != 0:
                explain.append(
                    f"{available} {claz.display_name()} utilities available."
                )
        return explain
