from __future__ import annotations

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class ReligionController(feature_controller.FeatureController):
    definition: defs.Religion
    supports_child_purchases: bool = True

    def can_afford(self, value: int = 1) -> Decision:
        if self.character.religion:
            return Decision.NO
        return Decision.OK
