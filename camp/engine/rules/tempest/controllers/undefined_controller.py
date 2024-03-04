from __future__ import annotations

from typing import Type

from camp.engine.rules import base_engine
from camp.engine.rules.base_models import Issue
from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class UndefinedFeatureController(feature_controller.FeatureController):
    definition: None = None
    child_ids: frozenset[str] = frozenset()
    parent: None = None
    parent_def: None = None
    supersedes: None = None
    superseded_by: None = None
    meets_requirements: Decision = Decision.OK
    tags: set[str] = frozenset({"Undefined"})
    description: str = "This feature isn't defined."
    short_description: str = description
    max_ranks: int = 101
    option_def: None = None
    category: None = None
    category_priority: float = 999.0
    feature_type: str = "unknown"
    currency: None = None
    cost_def: None = None
    explain: list[str] = []
    discounted_features: list[(feature_controller.FeatureController, int)] = []
    choices: None = None
    choice_defs: None = None
    supports_child_purchases: bool = False
    child_purchase_limit: None = None

    @classmethod
    def _definition_type(cls) -> Type[defs.BaseFeatureDef]:
        return type(None)

    @property
    def option(self) -> str | None:
        return self.expr.option

    def power_card(self) -> defs.PowerCard | None:
        return None

    def sub_cards(self) -> list[defs.PowerCard]:
        return []

    def can_increase(self, value: int = 1) -> Decision:
        return Decision.NO

    def _gather_propagation(self) -> dict[str, base_engine.PropagationData]:
        return {}

    def issues(self) -> list[Issue] | None:
        return [
            Issue(
                issue_code="undefined-feature",
                reason=f"Feature {self.display_name()} is not defined, please remove it.",
                feature_id=self.full_id,
            )
        ]
