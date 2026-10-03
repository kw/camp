from __future__ import annotations

from typing import Literal

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class CantripController(feature_controller.FeatureController):
    definition: defs.Cantrip

    def _cantrips_available(self) -> int:
        if self.parent and self.parent.feature_type == "class":
            purchased = self.parent.cantrips_purchased()
            cantrips = self.parent.cantrips_awarded()
            return cantrips - purchased
        return 0

    @property
    def sphere(self) -> Literal["arcane", "divine", "dual"]:
        return self.definition.sphere

    def can_afford(self, value: int = 1) -> Decision:
        available = self._cantrips_available()
        if available >= value:
            return Decision.OK
        elif self.parent:
            return Decision(
                success=False,
                reason=f"Already purchased max {self.parent.display_name()} cantrips",
                amount=max(available, 0),
            )
        else:
            return Decision(success=False)

    def explain_category_group(self) -> str | None:
        return f"{self._cantrips_available()} {self.category} available"

    @property
    def explain_list(self) -> list[str]:
        explain = []
        for claz in self.character.classes:
            available = claz.cantrips_awarded() - claz.cantrips_purchased()
            if available != 0:
                explain.append(f"{available} {claz.display_name()} cantrips available.")
        return explain
