from __future__ import annotations

from functools import cached_property
from typing import Literal

from camp.engine.rules import base_engine
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.decision import Decision

from .. import defs
from . import character_controller
from . import feature_controller
from . import spellbook_controller


class ClassController(feature_controller.FeatureController):
    character: character_controller.TempestCharacter
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
        """Is this currently the archetype class?"""
        return self.model.is_archetype_class

    @property
    def is_legal_archetype(self) -> bool:
        """Could this be chosen as the archetype class?"""
        if self.class_type != "basic":
            return False
        return self in self.character.archetype_legal_classes

    @property
    def innate_powers(self) -> list[feature_controller.FeatureController]:
        return (fc for fc in self.children if fc.definition.type == "innate")

    @property
    def archetype_powers(self) -> list[feature_controller.FeatureController]:
        return (fc for fc in self.children if fc.definition.type == "archetype")

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

    def cantrips_purchased(self) -> int:
        if not self.caster:
            return 0
        return sum(
            1
            for c in self.taken_children
            if c.feature_type == "cantrip" and c.purchased_ranks > 0
        )

    def spells_purchased(self) -> int:
        if not self.caster:
            return 0
        return sum(
            1
            for c in self.taken_children
            if c.feature_type == "spell" and c.purchased_ranks > 0
        )

    @cached_property
    def spellbook(self) -> spellbook_controller.SpellbookController | None:
        if self.caster:
            return self.character.controller(f"{self.sphere}.spellbook")
        return None

    @property
    def spellbook_available(self) -> int:
        if spellbook := self.spellbook:
            available_dict = spellbook.spells_available_per_class
            return available_dict.get(self.full_id, 0) + available_dict.get(None, 0)
        return 0

    @cached_property
    def powerbook(self) -> spellbook_controller.PowerbookController | None:
        if self.martial:
            return self.character.controller("martial.powerbook")
        return None

    @property
    def powers_taken(self) -> spellbook_controller.TierTuple:
        return self.powerbook.powers_taken_per_class.get(
            self.full_id, spellbook_controller.EMPTY_TIER
        )

    @property
    def powers_available(self) -> spellbook_controller.TierTuple:
        return self.powerbook.powers_available_per_class.get(
            self.full_id, spellbook_controller.EMPTY_TIER
        )

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
        # Archetype features
        if self.is_archetype:
            for feature in self.archetype_powers:
                if feature.meets_requirements:
                    grants[feature.id] = 1
        return grants

    @property
    def explain(self) -> list[str]:
        lines = super().explain
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
                lines.append(
                    f"Spells that can be added to spellbook: {self.spellbook_available}"
                )
            else:
                lines.append(f"Utilities: {self.get('utilities')}")
                lines.append(
                    f"Powers: {self.get('powers@1')}/{self.get('powers@2')}/{self.get('powers@3')}/{self.get('powers@4')}"
                )
                powers_taken = self.powers_taken
                powers_available = self.powers_available
                lines.append(
                    f"Powers taken: {powers_taken[0]}/{powers_taken[1]}/{powers_taken[2]}/{powers_taken[3]}"
                )
                lines.append(
                    f"Powers available: {powers_available[0]}/{powers_available[1]}/{powers_available[2]}/{powers_available[3]}"
                )
        return lines

    @property
    def choices(self) -> dict[str, base_engine.ChoiceController]:
        choices = super().choices or {}
        if not self.is_archetype and self.is_legal_archetype:
            choices["archetype"] = ArchetypeChoiceController(self)
        return choices

    def __str__(self) -> str:
        if self.value > 0:
            return f"{self.definition.name} {self.value}"
        return self.definition.name


class ArchetypeChoiceController(base_engine.ChoiceController):
    """This controller is presented when a the player has a choice of archetypes available.

    Normally a character's archetype class is their highest-level base class, but when more than
    one class fits that requirement the player can choose among them.

    This choice is only presented on a class that could, at this minute, be your archetype.
    Many of the fields can therefore be hard-coded.
    """

    id = "archetype"
    name = "Archetype"
    description = (
        "Your highest-level base classes are eligible to become archetype classes."
    )
    limit = 1
    choices_remaining = 1
    advertise = False
    _class: ClassController

    def __init__(self, class_controller: ClassController):
        self._class = class_controller

    def available_choices(self) -> dict[str, str]:
        return {
            "set-archetype": f"Set {self._class.display_name()} as your archetype class"
        }

    def taken_choices(self) -> dict[str, int]:
        return {}

    def choose(self, choice: str) -> Decision:
        if choice != "set-archetype":
            return Decision(success=False, reason="Invalid choice")
        if self._class.is_archetype:
            return Decision(success=True, reason="Already the archetype class")
        if not self._class.is_legal_archetype:
            return Decision(success=False, reason="Not a legal archetype class")
        self._class.is_archetype = True
        return Decision.OK

    def unchoose(self, choice: str) -> Decision:
        return Decision.NO

    def update_propagation(self, *args, **kwargs) -> None:
        pass
