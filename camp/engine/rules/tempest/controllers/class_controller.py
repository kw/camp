from __future__ import annotations

from typing import Literal

from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.decision import Decision

from .. import defs
from . import character_controller
from . import feature_controller


class ClassController(feature_controller.FeatureController):
    definition: defs.ClassDef
    currency = None
    rank_name_labels: tuple[str, str] = ("level", "levels")

    def __init__(self, id: str, character: character_controller.TempestCharacter):
        super().__init__(id, character)
        if not isinstance(self.definition, defs.ClassDef):
            raise ValueError(
                f"Expected {id} to be a class, but was {type(self.definition)}"
            )

    @property
    def class_type(self) -> Literal["basic", "advanced", "epic"]:
        return self.definition.class_type

    @property
    def is_archetype(self) -> bool:
        return self.model.is_archetype_class

    @property
    def innate_powers(self) -> list[feature_controller.FeatureController]:
        return (fc for fc in self.children if fc.definition.type == "innate")

    @is_archetype.setter
    def is_archetype(self, value: bool) -> None:
        self.model.is_archetype_class = value
        if value:
            # There can be only one primary class
            for controller in self.character.classes:
                if controller.id != self.full_id:
                    controller.is_archetype = False

    @property
    def is_starting(self) -> bool:
        if self.character.level == 0:
            # If there are no classes, we're talking hyoptheticals,
            # so we'll assume this would be the starting class if purchased.
            return True
        return self.model.is_starting_class

    @property
    def next_value(self) -> int:
        if self.value == 0 and self.character.level == 0:
            return 2
        return super().next_value

    @property
    def min_value(self) -> int:
        if self.is_starting and self.character.is_multiclass:
            return 2
        return super().min_value

    @is_starting.setter
    def is_starting(self, value: bool) -> None:
        self.model.is_starting_class = value
        if value:
            # There can be only one starting class
            for controller in self.character.classes:
                if controller.id != self.full_id:
                    controller.is_starting = False

    @property
    def sphere(self) -> str:
        return self.definition.sphere

    @property
    def martial(self) -> bool:
        return self.definition.sphere == "martial"

    @property
    def arcane(self) -> bool:
        return self.definition.sphere == "arcane"

    @property
    def divine(self) -> bool:
        return self.definition.sphere == "divine"

    @property
    def caster(self) -> bool:
        return self.definition.sphere != "martial"

    def spell_slots(self, expr: PropExpression) -> int:
        if not self.caster:
            return 0
        if expr is None or expr.slot is None:
            return sum(
                self.spell_slots(expr.copy(update={"slot": t})) for t in (1, 2, 3, 4)
            )
        slot = int(expr.slot)
        if 1 <= slot <= 4:
            tier_table = self.character.ruleset.powers[slot]
            return tier_table.evaluate(self.value)
        raise ValueError(f"Invalid spell slot tier: {expr}")

    def spells_prepared(self) -> int:
        if not self.caster:
            return 0
        return self.character.ruleset.spells_prepared.evaluate(self.value)

    def spells_known(self) -> int:
        if not self.caster:
            return 0
        return self.character.ruleset.spells_known.evaluate(self.value)

    def cantrips(self) -> int:
        if not self.caster:
            return 0
        return self.character.ruleset.powers[0].evaluate(self.value)

    def powers(self, expr: PropExpression) -> int:
        if self.caster:
            return 0
        if expr is None or expr.slot is None:
            return sum(self.powers(expr.copy(update={"slot": t})) for t in (1, 2, 3, 4))
        slot = int(expr.slot)
        if 1 <= slot <= 4:
            tier_table = self.character.ruleset.powers[slot]
            return tier_table.evaluate(self.value)
        raise ValueError(f"Invalid power tier: {expr}")

    def utilities(self) -> int:
        if self.caster:
            return 0
        return self.character.ruleset.powers[0].evaluate(self.value)

    def can_afford(self, value: int = 1) -> Decision:
        character_available = self.character.levels_available
        available = min(character_available, self.purchaseable_ranks)
        return Decision(success=available >= value, amount=available)

    def increase(self, value: int) -> Decision:
        if self.character.level == 0 and value < 2:
            # This is the character's first class. Ensure at least 2 ranks are purchased.
            value = 2
        if not (rd := super().increase(value)):
            return rd
        if (
            not self.is_archetype
            and max(
                (c.value for c in self.character.classes if c.id != self.id), default=0
            )
            < self.purchased_ranks
        ):
            self.is_archetype = True
        if self.character.starting_class is None:
            self.is_starting = True
        self.reconcile()
        return rd

    def can_decrease(self, value: int = 1) -> Decision:
        if not (rd := super().can_decrease(value)):
            return rd
        current = self.purchased_ranks
        # If this is the starting class, it can't be reduced below level 2
        # unless it's the only class on the sheet.
        if self.is_starting and current != self.character.level.value:
            if current - value < 2:
                return Decision(
                    success=False,
                    amount=(current - 2),
                    reason="Can't reduce starting class levels below 2 while multiclassed.",
                )
        return Decision(success=current >= value, amount=current)

    def decrease(self, value: int) -> Decision:
        current = self.purchased_ranks
        if self.is_starting and current - value < 2:
            # The starting class can't be reduced to level 1, only removed entirely.
            value = current
        if not (rd := super().decrease(value)):
            return rd
        if self.model.ranks <= 0:
            self.model.is_starting_class = False
            self.model.is_archetype_class = False
        if (
            self.is_archetype
            and max((c.value for c in self.character.classes), default=0)
            > self.purchased_ranks
        ):
            # TODO: Auto-set to the new highest
            pass
        self.reconcile()
        return Decision(success=True, amount=self.value)

    def extra_grants(self) -> dict[str, int]:
        # Base classes grant different starting features based on whether it's your starting class.
        grants = {}
        # Starting features
        if self.is_starting:
            grants.update(self._gather_grants(self.definition.starting_features))
        else:
            grants.update(self._gather_grants(self.definition.multiclass_features))
        # Innate features
        for feature in self.innate_powers:
            if feature.meets_requirements:
                grants[feature.id] = 1
        return grants

    def explain(self) -> list[str]:
        lines = super().explain()
        if self.value > 0:
            if self.is_starting:
                lines.append("This is your starting class.")
            if self.is_archetype:
                lines.append("This is your archetype class.")
            if self.caster:
                lines.append(
                    f"Spellcasting sphere: {self.character.display_name(self.sphere)}"
                )
                lines.append(f"Cantrips: {self.get('cantrips')}")
                lines.append(
                    f"Spell slots: {self.get('spell_slots@1')}/{self.get('spell_slots@2')}/{self.get('spell_slots@3')}/{self.get('spell_slots@4')}"
                )
                lines.append(f"Spells prepared: {self.get('spells_prepared')}")
                lines.append(f"Spells known: {self.get('spells_known')}")
            else:
                lines.append(f"Utilities: {self.get('utilities')}")
                lines.append(
                    f"Powers: {self.get('powers@1')}/{self.get('powers@2')}/{self.get('powers@3')}/{self.get('powers@4')}"
                )
        return lines

    def __str__(self) -> str:
        if self.value > 0:
            return f"{self.definition.name} {self.value}"
        return self.definition.name
