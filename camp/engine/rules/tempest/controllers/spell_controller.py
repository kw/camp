from __future__ import annotations

from typing import Any
from typing import Literal

from camp.engine.rules.decision import Decision

from .. import defs
from . import feature_controller


class SpellController(feature_controller.FeatureController):
    definition: defs.Spell
    can_buy_without_parent: bool = True

    @property
    def sphere(self) -> Literal["arcane", "divine", None]:
        return self.definition.sphere

    @property
    def tier(self) -> int | None:
        return self.definition.tier

    def sort_key(self) -> Any:
        return (self.tier, self.display_name())

    @property
    def category_priority(self) -> float:
        return super().category_priority + (self.tier or 0)

    def _spells_available(self) -> int:
        if self.parent and self.parent.feature_type == "class":
            return self.parent.spellbook_available
        # TODO: Handle spells from other sources.
        return 0

    def can_afford(self, value: int = 1) -> Decision:
        # Spells of greater than 1st tier are (generally) not available to add to your
        # spellbook until you have spell slots of that tier from that class.
        if self.tier and self.tier > 1:
            if not self.character.meets_requirements(
                f"{self.sphere}.spell_slots@{self.tier}"
            ):
                return Decision(
                    success=False,
                    reason=f"Cannot purchase {self.display_name()} until you have spell slots of that tier.",
                )
        if self._spells_available() >= value:
            return Decision.OK
        elif self.parent:
            return Decision(
                success=False,
                reason=f"Already purchased max {self.parent.display_name()} spells",
            )
        else:
            return Decision(success=False)

    @property
    def explain_category_group(self) -> str | None:
        return f"{self._spells_available()} {self.category} available"

    @property
    def formal_name(self) -> str:
        return f"{self.display_name()} [{self.type_name}]"

    @property
    def feature_list_name(self) -> str:
        """Used in contexts where the type of the feature can be assumed, such as the main feature type lists on the character display.

        Subclasses may still add more details. For example, in a giant list of spells, it's likely still useful to note the class and tier.
        """
        if tier := self.tier_name:
            if self.parent:
                return f"{self.display_name()} [{tier} {self.parent.display_name()}]"
            return f"{self.display_name()} [{tier}]"
        return super().feature_list_name

    @property
    def type_name(self) -> str:
        if tier := self.tier_name:
            if self.parent:
                return f"{tier} {self.parent.display_name()}"
            return tier
        return super().formal_name

    @property
    def tier_name(self) -> str | None:
        if self.tier is not None:
            if tier_names := self.character.ruleset.attribute_map[
                "spell_slots"
            ].tier_names:
                return tier_names[self.tier - 1]
        return None

    @property
    def explain_list(self) -> list[str]:
        explain = []
        for spellbook in self.character.spellbooks:
            available = spellbook.spells_available_per_class
            for claz, count in available.items():
                if claz is None and count != 0:
                    explain.append(
                        f"{count} {self.character.display_name(spellbook.sphere)} spells available."
                    )
                elif count != 0:
                    explain.append(
                        f"{count} {self.character.display_name(claz)} spells available."
                    )
        return explain
