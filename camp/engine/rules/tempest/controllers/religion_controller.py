from __future__ import annotations

from camp.engine.rules.decision import Decision
from camp.engine.rules.tempest.controllers.devotion_controller import DevotionController

from .. import defs
from . import feature_controller


class ReligionController(feature_controller.FeatureController):
    definition: defs.Religion
    supports_child_purchases: bool = True

    def can_afford(self, value: int = 1) -> Decision:
        if self.character.religion:
            return Decision.NO
        return Decision.OK

    def level_label(self) -> str:
        devs = self.devotions()
        if devs:
            match devs[-1].level_value:
                case 2:
                    return "Advanced"
                case 1:
                    return "Basic"
        return ""

    def devotions(self) -> list[DevotionController]:
        devs = [
            d
            for d in self.subfeatures
            if d.value > 0 and isinstance(d, DevotionController)
        ]
        devs.sort(key=lambda d: d.level_value)
        return devs
