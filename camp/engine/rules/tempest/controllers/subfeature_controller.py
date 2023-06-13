from __future__ import annotations

from camp.engine.rules.decision import Decision

from .. import defs
from .. import models
from . import character_controller
from . import feature_controller

_NO_PURCHASE = Decision(success=False)


class SubfeatureController(feature_controller.FeatureController):
    definition: defs.SubFeatureDef
    model_type = models.FeatureModel
    model: models.FeatureModel
    currency = None

    def __init__(self, id: str, character: character_controller.TempestCharacter):
        super().__init__(id, character)
        if not isinstance(self.definition, defs.SubFeatureDef):
            raise ValueError(
                f"Expected {id} to be a subfeature, but was {type(self.definition)}"
            )

    @property
    def type_name(self) -> str:
        if self.definition.display_type:
            return self.definition.display_type
        return super().type_name

    def can_increase(self, value: int = 1) -> Decision:
        return _NO_PURCHASE

    def increase(self, value: int) -> Decision:
        return _NO_PURCHASE

    def decrease(self, value: int) -> Decision:
        return _NO_PURCHASE
