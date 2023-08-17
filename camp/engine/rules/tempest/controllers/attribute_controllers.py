from __future__ import annotations

from typing import Iterable

from camp.engine.rules import base_engine
from camp.engine.rules.base_engine import CharacterController


class AttributeController(base_engine.AttributeController):
    @property
    def value(self):
        return sum(p.grants for p in self._propagation_data.values())


class LifePointController(AttributeController):
    @property
    def value(self):
        return super().value + self.character.base_lp


class SumAttribute(AttributeController):
    """Represents an attribute that aggregates over particular types of features.

    For example, the "caster" attribute measures the number of levels of spellcasting
    classes the character has taken, usually for requirements specified like
    "At least 5 levels in spellcasting classes" (and written "caster:5" in definition files).
    The `max_value` field implements requirements like "At least 5 levels in a spellcasting class",

    """

    character: base_engine.CharacterController
    _condition: str | None
    _feature_type: str

    def __init__(
        self,
        prop_id: str,
        character: base_engine.CharacterController,
        feature_type: str | None = None,
        condition: str | None = None,
    ):
        super().__init__(prop_id, character)
        self._condition = condition
        self._feature_type = feature_type

    @property
    def value(self) -> int:
        total: int = super().value
        for fc in self.matching_controllers():
            total += fc.value
        return total

    @property
    def max_value(self) -> int:
        current: int = 0
        for fc in self.matching_controllers():
            if (v := fc.value) > current:
                current = v
        return current

    def matching_controllers(self) -> Iterable[base_engine.BaseFeatureController]:
        for fc in self.character.features.copy().values():
            if self._feature_type and fc.feature_type != self._feature_type:
                continue
            if self._condition is None or getattr(fc, self._condition, True):
                yield fc


class CharacterPointController(AttributeController):
    character: base_engine.CharacterController

    @property
    def value(self) -> int:
        base = self.character.awarded_cp + self.character.base_cp + super().value

        return base + self.flaw_award_cp - self.spent_cp

    @property
    def spent_cp(self) -> int:
        return self.purchase_spent_cp + self.flaw_overcome_cp

    @property
    def purchase_spent_cp(self) -> int:
        spent: int = 0
        for feat in self.character.features.copy().values():
            if feat.currency == "cp":
                spent += feat.cost
        return spent

    @property
    def flaw_cp_cap(self) -> int:
        return self.character.ruleset.flaw_cp_cap

    @property
    def flaw_award_cp(self) -> int:
        # If a flaw was elected by the player, there is a cap
        # to the amount of points they can gain from it.
        # On the other hand, if plot applies the flaw and is 'nice'
        # enough to award points for it, those bypass the cap.
        player_total: int = 0
        plot_total: int = 0
        for flaw in self.character.flaws.values():
            if flaw.model.plot_added:
                plot_total += flaw.award_cp
            else:
                player_total += flaw.award_cp
        return min(player_total, self.flaw_cp_cap) + plot_total

    @property
    def flaw_cp_available(self) -> int:
        return self.flaw_cp_cap - self.flaw_award_cp

    @property
    def flaw_overcome_cp(self) -> int:
        total: int = 0
        for flaw in list(self.character.flaws.values()):
            total += flaw.overcome_cp
        return total


class BreedPointController(AttributeController):
    character: base_engine.CharacterController
    primary: bool

    def __init__(self, primary: bool, character: CharacterController):
        super().__init__("bp-primary" if primary else "bp-secondary", character)
        self.primary = primary

    @property
    def breed(self) -> base_engine.BaseFeatureController | None:
        return (
            self.character.primary_breed
            if self.primary
            else self.character.secondary_breed
        )

    @property
    def bp_cap(self) -> int:
        return (
            self.character.ruleset.breed_primary_bp_cap
            if self.primary
            else self.character.ruleset.breed_secondary_bp_cap
        )

    @property
    def awarded_bp(self) -> int:
        return min(self.bp_cap, self.challenge_award_bp) + self.bonus

    @property
    def challenge_award_bp(self) -> int:
        total: int = 0
        if breed := self.breed:
            for challenge in breed.taken_challenges:
                total += challenge.award_bp
        return total

    @property
    def advantage_cost_bp(self) -> int:
        total: int = 0
        if breed := self.breed:
            for advantage in breed.taken_advantages:
                total += advantage.cost
        return total

    @property
    def value(self) -> int:
        return self.awarded_bp - self.advantage_cost_bp
