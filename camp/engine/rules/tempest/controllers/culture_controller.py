from __future__ import annotations

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class CultureController(feature_controller.FeatureController):
    definition: defs.Culture

    def can_afford(self, value: int = 1) -> Decision:
        if self.character.culture:
            return Decision.NO
        return Decision.OK
