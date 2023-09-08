from __future__ import annotations

from functools import cached_property
from typing import Any

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class PowerController(feature_controller.FeatureController):
    definition: defs.Power

    @property
    def tier(self) -> int | None:
        return self.definition.tier

    @property
    def category_priority(self) -> float:
        return super().category_priority + (self.tier or 0)

    def sort_key(self) -> Any:
        return (self.tier, self.display_name())

    @property
    def _powers_available(self) -> int:
        if (
            self.parent
            and self.parent.feature_type == "class"
            and self.tier is not None
        ):
            return self.parent.powers_available[self.tier - 1]
        # At this time, martial powers from other sources are not supported.
        return 0

    @property
    def _higher_tier_available(self) -> int:
        if (
            self.parent
            and self.parent.feature_type == "class"
            and self.tier is not None
            and self.tier < 3
        ):
            return sum(self.parent.powers_available[self.tier :])
        return 0

    def can_afford(self, value: int = 1) -> Decision:
        if (self._powers_available + self._higher_tier_available) >= value:
            return Decision.OK
        return Decision(success=False)

    @property
    def explain_category_group(self) -> str | None:
        if self._powers_available > 0:
            return f"{self._powers_available} {self.category} available"
        else:
            return f"{self.category} using up to {self._higher_tier_available} higher-tier slots"

    @property
    def formal_name(self) -> str:
        return f"{self.display_name()} [{self.type_name}]"

    @cached_property
    def tags(self) -> set[str]:
        tags = super().tags
        if self.tier:
            return tags | {self.tier_name}
        return tags

    @property
    def category_tags(self) -> set[str]:
        return super().category_tags | {self.tier_name}

    @property
    def tier_name(self) -> str | None:
        if self.tier is not None:
            if tier_names := self.character.ruleset.attribute_map["powers"].tier_names:
                return tier_names[self.tier - 1]
        return None

    @property
    def explain_list(self) -> list[str]:
        explain = []
        if powerbook := self.character.powerbook:
            available = powerbook.powers_available_per_class
            for claz, tiers in available.items():
                class_name = self.character.display_name(claz)
                for i, count in enumerate(tiers):
                    if count != 0:
                        explain.append(
                            f"{count} {class_name} {self.character.ruleset.attribute_map['powers'].tier_names[i]} powers available."
                        )
                    elif sum(tiers[i:]) > 0:
                        explain.append(
                            f"{class_name} {self.character.ruleset.attribute_map['powers'].tier_names[i]} powers can be taken using higher-tier slots."
                        )
        return explain
