from __future__ import annotations

from functools import cached_property
from typing import Literal

from camp.engine.rules import base_engine
from camp.engine.rules.base_models import Discount
from camp.engine.rules.base_models import Issue
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.base_models import Table
from camp.engine.rules.decision import Decision

from .. import defs
from . import character_controller
from . import choice_controller
from . import feature_controller
from . import spellbook_controller


class ClassController(feature_controller.FeatureController):
    character: character_controller.TempestCharacter
    definition: defs.ClassDef
    currency = None
    rank_name_labels: tuple[str, str] = ("level", "levels")

    @property
    def class_type(self) -> Literal["basic", "advanced", "epic"]:
        return self.definition.class_type

    @cached_property
    def extensions(self) -> list[ClassController]:
        ext: list[ClassController] = []
        for expr in self.definition._extension_ids:
            fc = self.character.feature_controller(expr)
            ext.append(fc)

        return ext

    @cached_property
    def extends(self) -> ClassController | None:
        if self.definition.extends:
            return self.character.feature_controller(self.definition.extends)
        return None

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
        return self.definition.sphere == "martial" or self.definition.powers is not None

    @property
    def dual(self) -> bool:
        return self.definition.sphere == "dual"

    @property
    def arcane(self) -> bool:
        return self.definition.sphere == "arcane" or self.dual

    @property
    def divine(self) -> bool:
        return self.definition.sphere == "divine" or self.dual

    @property
    def caster(self) -> bool:
        return (
            self.definition.sphere != "martial"
            or self.definition.spells is not None
            or self.definition.spells_known is not None
        )

    @property
    def _ranks_tag(self) -> str:
        return f"{self.value}"

    @property
    def _max_ranks_tag(self) -> str:
        return f"{self.max_ranks} levels"

    @property
    def extension_value(self) -> int:
        return self.value + sum(ex.value for ex in self.extensions)

    @cached_property
    def _spell_table(self) -> dict[int, Table]:
        if isinstance(self.definition.spells, dict):
            return self.definition.spells
        elif self.definition.extends:
            # Extension classes don't have their own tables.
            return {}
        elif self.class_type == "basic":
            return self.character.ruleset.spells
        elif self.class_type == "advanced":
            return self.character.ruleset.ac_spells
        else:
            raise NotImplementedError

    @cached_property
    def _spells_known_table(self) -> Table | None:
        if self.definition.extends:
            # Extension classes don't have their own tables.
            return None
        if isinstance(self.definition.spells_known, Table):
            return self.definition.spells_known
        return self.character.ruleset.spells_known

    @cached_property
    def _power_table(self) -> dict[int, Table]:
        if isinstance(self.definition.powers, dict):
            return self.definition.powers
        elif self.definition.extends:
            # Extension classes don't have their own tables.
            return {}
        elif self.class_type == "basic":
            return self.character.ruleset.powers
        elif self.class_type == "advanced":
            return self.character.ruleset.ac_powers
        else:
            raise NotImplementedError

    def spell_slots(self, expr: PropExpression) -> int:
        if self.value <= 0 or not self.caster:
            return 0
        if expr.slot is None:
            return sum(
                self.spell_slots(expr.model_copy(update={"slot": t}))
                for t in (1, 2, 3, 4)
            )
        slot = int(expr.slot)
        if 1 <= slot <= 4:
            tier_table = self._spell_table.get(slot)
            if not tier_table:
                return 0
            return tier_table.evaluate(self.extension_value)
        raise ValueError(f"Invalid spell slot tier: {expr}")

    def spells_known(self) -> int:
        if self.value <= 0 or not self.caster:
            return 0
        if t := self._spells_known_table:
            return t.evaluate(self.extension_value)
        return 0

    def cantrips(self) -> int:
        if self.value <= 0 or not self.caster:
            return 0
        if table := self._spell_table.get(0):
            return table.evaluate(self.extension_value)
        return 0

    def cantrips_awarded(self) -> int:
        if not self.caster:
            return 0
        return self.character.get(f"{self.full_id}.cantrips")

    def cantrips_purchased(self) -> int:
        if not self.caster:
            return 0
        return sum(
            c.paid_ranks
            for c in self.taken_children
            if c.feature_type == "cantrip" and c.purchased_ranks > 0
        )

    def spells_purchased(self) -> int:
        if not self.caster:
            return 0
        return sum(
            c.paid_ranks for c in self.taken_children if c.feature_type == "spell"
        )

    def utilities_purchased(self) -> int:
        if not self.martial:
            return 0
        return sum(
            c.paid_ranks for c in self.taken_children if c.feature_type == "utility"
        )

    def utilities_awarded(self) -> int:
        if not self.martial:
            return 0
        return self.character.get(f"{self.full_id}.utilities")

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
        if not self.powerbook:
            return spellbook_controller.EMPTY_TIER
        return self.powerbook.powers_taken_per_class.get(
            self.full_id, spellbook_controller.EMPTY_TIER
        )

    @property
    def powers_available(self) -> spellbook_controller.TierTuple:
        if not self.powerbook:
            return spellbook_controller.EMPTY_TIER
        return self.powerbook.powers_available_per_class.get(
            self.full_id, spellbook_controller.EMPTY_TIER
        )

    def issues(self) -> list[Issue] | None:
        issues = super().issues() or []
        # Are too many powers taken?
        # This should be checked whether or not the class has actually been taken,
        # since a player could take a class, take powers from it, and then remove
        # the class.
        for i, available in enumerate(self.powers_available):
            if available < 0:
                issues.append(
                    Issue(
                        issue_code="too-many-powers",
                        reason=f"Too many tier {i+1} or lower {self.display_name()} powers taken ({abs(available)}). Please remove some.",
                    )
                )

        utilities_available = self.utilities_awarded() - self.utilities_purchased()
        if utilities_available < 0:
            issues.append(
                Issue(
                    issue_code="too-many-powers",
                    reason=f"Too many {self.display_name()} utility powers taken ({abs(utilities_available)}). Please remove some.",
                )
            )

        cantrips_available = self.cantrips_awarded() - self.cantrips_purchased()
        if cantrips_available < 0:
            issues.append(
                Issue(
                    issue_code="too-many-powers",
                    reason=f"Too many {self.display_name()} cantrips taken ({abs(cantrips_available)}). Please remove some.",
                )
            )

        return issues

    def powers(self, expr: PropExpression) -> int:
        if self.value <= 0 or not self.martial:
            return 0
        if expr is None or expr.slot is None:
            return sum(
                self.powers(expr.model_copy(update={"slot": t})) for t in (1, 2, 3, 4)
            )
        slot = int(expr.slot)
        if 1 <= slot <= 4:
            tier_table = self._power_table.get(slot)
            if not tier_table:
                return 0
            return tier_table.evaluate(self.extension_value)
        raise ValueError(f"Invalid power tier: {expr}")

    def utilities(self) -> int:
        if self.value <= 0 or not self.martial:
            return 0
        if table := self._power_table.get(0):
            return table.evaluate(self.extension_value)
        return 0

    def can_afford(self, value: int = 1) -> Decision:
        character_available = self.character.levels_available
        available = min(character_available, self.purchaseable_ranks)
        if (
            self.class_type == "advanced"
            and self.value == 0
            and self.character.advanced_classes >= 3
        ):
            return Decision.NO
        if (
            self.class_type == "epic"
            and self.value == 0
            and self.character.epic_classes > 0
        ):
            return Decision.NO
        return Decision(success=available >= value, amount=available)

    def increase(self, value: int) -> Decision:
        if self.character.level == 0 and value < 2:
            # This is the character's first class. Ensure at least 2 ranks are purchased.
            value = 2
        if not (rd := super().increase(value)):
            return rd
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
        return grants

    @property
    def specialization_counts(self) -> dict[str, int]:
        """Return a dict mapping specialization IDs to the number of times they're taken."""
        tags = self.definition.specializations
        if tags is None:
            return {}
        counts = {tag: 0 for tag in tags}
        features = self.character.features.copy()
        for feature in features.values():
            for tag in tags:
                if tag in feature.tags:
                    counts[tag] += feature.value
        return counts

    @property
    def specialization_tied(self) -> bool:
        """Return True if there's a tie for the most specialization tag counts."""
        spec_count = self.specialization_counts
        if not spec_count:
            return False
        max_taken = max(spec_count.values())
        if max_taken == 0:
            return False
        return len([tag for tag, count in spec_count.items() if count == max_taken]) > 1

    @property
    def current_specialization(self) -> tuple[str, int] | None:
        spec_count = self.specialization_counts
        if not spec_count:
            return None
        max_taken = max(spec_count.values())
        max_tags = [tag for tag, count in spec_count.items() if count == max_taken]
        if len(max_tags) == 1:
            return max_tags[0], max_taken
        elif self.model.choices and (
            tiebreaker := self.model.choices.get("specialization")
        ):
            spec = tiebreaker[0]
            if spec in max_tags:
                return spec, max_taken
        return None

    def specialization(self, expr: PropExpression) -> int:
        if spec := self.current_specialization:
            if expr.option == spec[0]:
                return spec[1]
        return 0

    @property
    def explain(self) -> list[str]:
        lines = super().explain
        character = self.character
        if self.value > 0:
            if self.is_starting:
                lines.append("This is your starting class.")
            if ext := self.extends:
                lines.append(f"Extends [{ext.display_name()}](../{ext.id})")
            elif (ext_value := self.extension_value) and ext_value != self.value:
                lines.append(f"Extended by {ext_value - self.value} levels by:\n")
                lines.extend(
                    f"- [{e.display_name()}](../{e.id}) ({e.value})"
                    for e in self.extensions
                )
                lines.append("\n")

            if self.caster and not ext:
                lines.append(
                    f"Spellcasting sphere: {character.display_name(self.sphere)}"
                )
                lines.append(f"Cantrips: {character.get(f'{self.id}.cantrips')}")
                lines.append(
                    f"Spell slots: {character.get(f'{self.id}.spell_slots@1')}/{character.get(f'{self.id}.spell_slots@2')}/{character.get(f'{self.id}.spell_slots@3')}/{character.get(f'{self.id}.spell_slots@4')}"
                )
                lines.append(
                    f"Spells that can be added to spellbook: {self.spellbook_available}"
                )
            if self.martial and not ext:
                lines.append(f"Utilities: {character.get(f'{self.id}.utilities')}")
                lines.append(
                    f"Powers: {character.get(f'{self.id}.powers@1')}/{character.get(f'{self.id}.powers@2')}/{character.get(f'{self.id}.powers@3')}/{character.get(f'{self.id}.powers@4')}"
                )
                powers_taken = self.powers_taken
                powers_available = self.powers_available
                lines.append(
                    f"Powers taken: {powers_taken[0]}/{powers_taken[1]}/{powers_taken[2]}/{powers_taken[3]}"
                )
                lines.append(
                    f"Powers available: {powers_available[0]}/{powers_available[1]}/{powers_available[2]}/{powers_available[3]}"
                )
        if spec := self.current_specialization:
            lines.append(
                f"{self.character.display_name(spec[0])}: {spec[1]} powers taken ⭐️"
            )

        # List counts for other specialization tags.
        for tag, count in self.specialization_counts.items():
            if not spec or spec[0] != tag:
                lines.append(
                    f"{self.character.display_name(tag)}: {count} powers taken"
                )
        return lines

    @property
    def choices(self) -> dict[str, base_engine.ChoiceController]:
        if self.value < 1:
            return {}
        choices = super().choices or {}
        if self.specialization_tied:
            choices["specialization"] = SpecializationChoiceController(self)
        if self.class_type == "advanced" and self.definition.extends is None:
            choices["tierswap"] = TierSwapChoiceController(self)
        return choices

    def sort_key(self):
        return (-self.value, self.display_name())

    def __str__(self) -> str:
        if self.value > 0:
            return f"{self.definition.name} {self.value}"
        return self.definition.name


class TierSwapChoiceController(choice_controller.ChoiceController):
    name = "Base Class Power Swap"
    description = "You may sacrifice a power or known spell from a base class to gain an appropriate slot for this class. After selection an option here, you will need to manually remove a spell or power from the chosen class."
    multi = True
    _class: ClassController

    @property
    def limit(self) -> int:
        return self._class.value

    def __init__(self, class_controller: ClassController):
        super().__init__(class_controller, "tierswap")
        self._class = class_controller

    def available_choices(self) -> dict[str, str]:
        choices = {}
        if self.choices_remaining <= 0:
            return choices
        character = self._class.character
        powers_available = self.categorize_powers_available()
        for claz in character.classes:
            if claz.id == self._class.id or claz.class_type != "basic":
                continue
            for p in powers_available:
                choice = f"{claz.id}.{p}"
                if character.get(choice) > 0:
                    choices[choice] = choice
        return choices

    def update_propagation(
        self, grants: dict[str, int], discounts: dict[str, list[Discount]]
    ) -> None:
        for choice, value in self.choice_ranks().items():
            expr = PropExpression.parse(choice)
            gain = expr.model_copy(update={"prefixes": (self._class.id,)})
            grants[expr.full_id] = -value
            grants[gain.full_id] = value

    def categorize_powers_available(self) -> set[str]:
        power_tiers = set()
        for child in self._class.children:
            # We only want to give the player the option to sacrifice for a
            # given type if the class actually has that type left to purchase.
            if child.max_attained:
                continue
            match child.feature_type:
                case "power":
                    if child.tier is not None:
                        power_tiers.add(f"powers@{child.tier}")
                case "utility":
                    power_tiers.add("utilities")
                case "spell":
                    power_tiers.add("spells_known")
                case "cantrip":
                    power_tiers.add("cantrips")
        return power_tiers


class SpecializationChoiceController(choice_controller.ChoiceController):
    """Breaks ties between specialization tag counts.

    This choice is only shown if the character has a tie for the most
    specialization tag counts. The player can choose among them which
    should be the specialization. The value is remembered if the tie
    is later broken and re-emerges. It can be un-chosen as long as the
    tie exists.
    """

    name = "Specialization"
    description = "You have a tie for the most specialization tag counts. Select which should be your specialization."
    limit = 1
    multi = False
    _class: ClassController

    def __init__(self, class_controller: ClassController):
        super().__init__(class_controller, "specialization")
        self._class = class_controller

    def available_choices(self) -> dict[str, str]:
        if self.taken_choices():
            return {}

        specs = self._class.specialization_counts
        max_count = max(specs.values())
        max_specs = {
            tag: self._class.character.display_name(tag)
            for tag, count in specs.items()
            if count == max_count
        }
        # We only show this choice if there's a tie for the most specialization tag counts.
        if len(max_specs) > 1:
            return max_specs
        return {}

    def update_propagation(
        self, grants: dict[str, int], discounts: dict[str, list[Discount]]
    ) -> None:
        pass
