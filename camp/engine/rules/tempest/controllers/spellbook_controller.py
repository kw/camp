from __future__ import annotations

from collections import defaultdict
from functools import cached_property

from camp.engine.rules import base_engine
from camp.engine.rules.base_models import PropExpression

from . import attribute_controllers

TierTuple = tuple[int, int, int, int]
EMPTY_TIER = (0, 0, 0, 0)


class SphereAttribute(attribute_controllers.SumAttribute):
    def __init__(self, prop_id: str, character: base_engine.CharacterController):
        super().__init__(prop_id, character, feature_type="class", condition=prop_id)

    def _evaluate_sphere_attr(self, expr: PropExpression) -> int:
        return sum(fc.subcontroller(expr).value for fc in self.matching_controllers())

    @property
    def sphere(self) -> str:
        return self.expression.prop

    spell_slots = _evaluate_sphere_attr
    spells_known = _evaluate_sphere_attr
    spells_prepared = _evaluate_sphere_attr
    cantrips = _evaluate_sphere_attr
    powers = _evaluate_sphere_attr
    utilities = _evaluate_sphere_attr

    @cached_property
    def spellbook(self) -> SpellbookController | None:
        if self.sphere != "martial":
            return SpellbookController("spellbook", self.sphere, self.character)
        return None

    @cached_property
    def powerbook(self) -> PowerbookController | None:
        if self.sphere == "martial":
            return PowerbookController("powerbook", self.character)
        return None


class PowerbookController(attribute_controllers.AttributeController):
    """The Powerbook controller keeps track of martial power capacity.

    It is essentially the martial version of SpellbookController.
    """

    @property
    def powers_taken(self) -> int:
        return sum(self.powers_taken_per_class.values()) + self.bonus

    @property
    def powers_earned_total(self) -> int:
        return sum(self.powers_earned_per_class.values())

    @property
    def value(self) -> int:
        return self.powers_earned_total

    @property
    def powers_available_per_class(self) -> dict[str, TierTuple]:
        """The number of powers from each class that can be added to the powerbook at this time."""
        powers_available: dict[str, TierTuple] = {}
        earned = self.powers_earned_per_class
        taken = self.powers_taken_per_class
        for class_id in self.martial_classes:
            class_earned = earned.get(class_id, EMPTY_TIER)
            class_taken = taken.get(class_id, EMPTY_TIER)
            if class_earned == EMPTY_TIER and class_taken == EMPTY_TIER:
                continue
            rollover = 0
            tiers = [0] * 4
            for i in range(len(class_earned)):
                available_this_tier = class_earned[i] - (class_taken[i] + rollover)
                # If we have used too many slots this tier but have earned slots in the
                # next tier, roll the powers over to that tier.
                if (
                    available_this_tier < 0
                    and i + 1 < len(class_earned)
                    and class_earned[i + 1] > 0
                ):
                    rollover = -available_this_tier
                    available_this_tier = 0
                else:
                    rollover = 0
                tiers[i] = available_this_tier
            powers_available[class_id] = tuple(tiers)
        return powers_available

    @property
    def powers_earned_per_class(self) -> dict[str, TierTuple]:
        counts: dict[str, TierTuple] = {}
        for class_id in self.martial_classes:
            tiers = [0] * 4
            for tier in range(1, 5):
                tiers[tier - 1] = self.character.get(f"{class_id}.powers@{tier}")
            counts[class_id] = tuple(tiers)
        return {k: v for k, v in counts.items() if any(v)}

    @property
    def powers_taken_per_class(self) -> dict[str, TierTuple]:
        """Count the number of martial powers taken per class, per tier."""
        counts: dict[str, list[int]] = defaultdict(lambda: [0] * 4)
        for fc in self.character.martial_powers:
            if fc.parent and fc.parent.feature_type == "class":
                counts[fc.parent.full_id][fc.tier - 1] += fc.value
        return {k: tuple(v) for k, v in counts.items() if any(v)}

    @property
    def martial_classes(self) -> set[str]:
        return {
            f.id
            for f in self.character.ruleset.features.values()
            if f.type == "class" and f.sphere == "martial"
        }


class SpellbookController(attribute_controllers.AttributeController):
    """The Spellbook controller keeps track of spellbook capacity.

    Specifically, it keeps track of how many spells of each class (in its sphere) are
    known compared to the base number of spells known for those classes, plus any
    bonuses from skills that increase the number of spells you can have in your spellbook.

    Why is this not tracked per-class? Each class grants a number of spells known that must
    come from that particular class. But the more generic skills instead let you take spells
    from any class in your sphere (simplifying a bit). So we need to track the number of
    spells taken from each class in the sphere so that we can attribute any overages to the generic
    slots
    """

    sphere: str

    def __init__(
        self,
        expr: str | PropExpression,
        sphere: str,
        character: base_engine.CharacterController,
    ):
        super().__init__(expr, character)
        self.sphere = sphere

    @property
    def spellbook_size(self) -> int:
        return sum(self._count_spells_known().values()) + self.bonus

    @property
    def spells_in_book(self) -> int:
        return sum(self._count_spells().values())

    @property
    def value(self) -> int:
        return self.spellbook_size

    @property
    def spells_available_per_class(self) -> dict[str | None, int]:
        """The number of spells from each class of this sphere that can be added to the spellbook.

        If there is a positive None entry, those spells can be added from any class in the sphere.
        Note that this is interpreted differently depending on whether you have any classes of that sphere.
        Sources of bonus spells normally have language along the lines of "You can choose a spell from any
        class in this sphere if you don't have one, otherwise you must choose from a class you do have".

        If there is a negative None entry, those spells must be removed from the spellbook. This usually
        only happens if you gain the Sourcerer class while already having an arcane spellbook.
        """
        free_spells = self.bonus
        free_used = 0
        spells_known = self._count_spells_known()
        spells_in_book = self._count_spells()
        spells_available: dict[str | None, int] = {}
        for claz in self.classes_in_sphere:
            available = spells_known.get(claz, 0) - spells_in_book.get(claz, 0)
            if available >= 0:
                # All spells known of this class fit into the class's spells known quota.
                spells_available[claz] = available
            else:
                # We need to use some of the global free spells to account for this class's spells.
                free_used += -available
        spells_available[None] = free_spells - free_used
        return spells_available

    @property
    def excess_spells(self) -> int:
        if (excess := self.spells_in_book - self.spellbook_size) > 0:
            return excess
        return 0

    def _count_spells(self) -> dict[str, int]:
        """Count the number of spells known from each class in the sphere.

        Only 'purchased' spells are counted, not spells granted by other means.

        Spells with no parent are counted under None.
        """
        counts: dict[str | None, int] = defaultdict(int)
        for fc in self.character.spells:
            if (
                fc.sphere == self.sphere
                and fc.purchased_ranks > 0
                and fc.parent
                and fc.parent.feature_type == "class"
            ):
                counts[fc.parent.full_id] += 1
        return counts

    def _count_spells_known(self) -> dict[str, int]:
        """Count the number of spells known from each class in the sphere."""
        counts: dict[str, int] = defaultdict(int)
        for class_id in self.classes_in_sphere:
            counts[class_id] = self.character.get(f"{class_id}.spells_known")
        return counts

    @cached_property
    def classes_in_sphere(self) -> set[str]:
        """The set of classes in this sphere."""
        return {
            f.id
            for f in self.character.ruleset.features.values()
            if f.type == "class" and f.sphere == self.sphere
        }
