from __future__ import annotations

from camp.engine.rules import base_engine

from . import character_controller


class AttributeController(base_engine.AttributeController):
    character: character_controller.TempestCharacter

    def __init__(self, prop_id: str, character: character_controller.TempestCharacter):
        super().__init__(prop_id, character)

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

    character: character_controller.TempestCharacter
    _condition: str | None
    _feature_type: str

    def __init__(
        self,
        prop_id: str,
        character: character_controller.TempestCharacter,
        feature_type: str,
        condition: str | None = None,
    ):
        super().__init__(prop_id, character)
        self._condition = condition
        self._feature_type = feature_type

    @property
    def value(self) -> int:
        total: int = super().value
        for fc in self.character.controllers_for_type(self._feature_type).values():
            if self._condition is None or getattr(fc, self._condition, True):
                total += fc.value
        return total

    @property
    def max_value(self) -> int:
        current: int = 0
        for fc in self.character.controllers_for_type(self._feature_type).values():
            if (self._condition is None or getattr(fc, self._condition, True)) and (
                v := fc.value
            ) > current:
                current = v
        return current


class CharacterPointController(AttributeController):
    character: character_controller.TempestCharacter

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
        for feat in list(self.character.features.values()):
            if feat.currency == "cp":
                spent += feat.cost
        return spent

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
        return min(player_total, self.character.ruleset.flaw_cp_cap) + plot_total

    @property
    def flaw_overcome_cp(self) -> int:
        total: int = 0
        for flaw in list(self.character.flaws.values()):
            total += flaw.overcome_cp
        return total
