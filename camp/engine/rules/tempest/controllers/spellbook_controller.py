from __future__ import annotations

from collections import defaultdict
from functools import cached_property

from camp.engine.rules import base_engine
from camp.engine.rules.base_models import PropExpression

from . import attribute_controllers


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
        spells_available: dict[str, None, int] = {}
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
