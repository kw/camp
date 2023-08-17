from __future__ import annotations

from typing import Literal

from camp.engine.rules.decision import Decision

from .. import defs
from . import character_controller
from . import feature_controller


class CantripController(feature_controller.FeatureController):
    definition: defs.Cantrip

    def __init__(self, full_id: str, character: character_controller.TempestCharacter):
        super().__init__(full_id, character)
        if not isinstance(self.definition, defs.Cantrip):
            raise ValueError(
                f"Expected {full_id} to be a cantrip but was {type(self.definition)}"
            )

    def _cantrips_available(self) -> int:
        if self.parent and self.parent.feature_type == "class":
            purchased = self.parent.cantrips_purchased()
            cantrips = self.character.get(f"{self.parent.full_id}.cantrips")
            return cantrips - purchased
        return 0

    @property
    def sphere(self) -> Literal["arcane", "divine", None]:
        return self.definition.sphere

    def can_afford(self, value: int = 1) -> Decision:
        if self._cantrips_available() >= value:
            return Decision.OK
        elif self.parent:
            return Decision(
                success=False,
                reason=f"Already purchased max {self.parent.display_name} cantrips",
            )
        else:
            return Decision(success=False)

    def explain_category_group(self) -> str | None:
        return f"{self._cantrips_available()} {self.category} available"
