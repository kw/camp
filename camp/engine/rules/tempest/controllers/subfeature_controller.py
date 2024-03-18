from __future__ import annotations

from camp.engine.rules.decision import Decision

from .. import defs
from .. import models
from . import feature_controller

_NO_PURCHASE = Decision(success=False, reason="")


class SubfeatureController(feature_controller.FeatureController):
    definition: defs.SubFeatureDef
    model_type = models.FeatureModel
    model: models.FeatureModel

    @property
    def currency(self) -> str | None:
        if self.definition.cost is not None:
            return "cp"
        return None

    @property
    def type_name(self) -> str:
        if self.definition.display_type:
            return self.definition.display_type
        return super().type_name

    @property
    def allow_purchases(self) -> bool:
        """Should this subfeature support purchase flows?

        Normally subfeatures are simply granted or not, but rarely the parent
        feature may declare that a number of subfeatures may be purchased.
        In those cases, subfeatures will use the normal purchase logic.
        If they have a
        """
        return self.parent and self.parent.supports_child_purchases

    @property
    def explain_category_group(self) -> str | None:
        if self.allow_purchases:
            return f"{self.parent.child_purchase_count} purchased of {self.parent.child_purchase_limit} allowed."
        return None

    def can_increase(self, value: int = 1) -> Decision:
        if self.allow_purchases:
            return super().can_increase(value)
        return _NO_PURCHASE

    def increase(self, value: int) -> Decision:
        if self.allow_purchases:
            return super().increase(value)
        return _NO_PURCHASE

    def decrease(self, value: int) -> Decision:
        if self.allow_purchases:
            return super().decrease(value)
        return _NO_PURCHASE
