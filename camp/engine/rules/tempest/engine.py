from __future__ import annotations

from abc import abstractmethod
from functools import cached_property
from typing import Literal
from typing import Type

from camp.engine.rules.base_models import Discount
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.decision import Decision

from .. import base_engine
from . import defs
from . import models
from .controllers import character_controller


class TempestEngine(base_engine.Engine):
    ruleset: defs.Ruleset
    sheet_type = models.CharacterModel

    @property
    def character_controller(self) -> Type[base_engine.CharacterController]:
        return character_controller.TempestCharacter

    @cached_property
    def class_defs(self) -> dict[str, defs.ClassDef]:
        return {
            k: f for (k, f) in self.feature_defs.items() if isinstance(f, defs.ClassDef)
        }

    @cached_property
    def skill_defs(self) -> dict[str, defs.SkillDef]:
        return {
            k: f for (k, f) in self.feature_defs.items() if isinstance(f, defs.SkillDef)
        }


class AttributeController(base_engine.AttributeController):
    character: character_controller.TempestCharacter

    def __init__(self, prop_id: str, character: character_controller.TempestCharacter):
        super().__init__(prop_id, character)

    @property
    def value(self):
        return sum(p.grants for p in self._propagation_data.values())


class ChoiceController(base_engine.ChoiceController):
    _feature: base_engine.BaseFeatureController
    _choice: str

    def __init__(self, feature: base_engine.BaseFeatureController, choice_id: str):
        self._feature = feature
        self._choice = choice_id

    @cached_property
    def definition(self) -> defs.ChoiceDef:
        return self._feature.definition.choices[self._choice]

    @cached_property
    def controller_data(self) -> dict:
        return self.definition.controller_data or {}

    @property
    def id(self) -> str:
        return self._choice

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def limit(self) -> int | Literal["unlimited"]:
        if isinstance(self.definition.limit, int) and self.definition.limit_is_per_rank:
            return self.definition.limit * self._feature.value
        return self.definition.limit

    @property
    def choices_remaining(self) -> int:
        if self.limit == "unlimited":
            return 999
        return self.limit - sum(self.choice_ranks().values())

    def taken_choices(self) -> dict[str, str]:
        taken = {}
        if choices := self._feature.model.choices.get(self._choice):
            for choice in choices:
                expr = PropExpression.parse(choice)
                taken[expr.full_id] = self.describe_choice(choice)
        return taken

    def choose(self, choice: str) -> Decision:
        choice_ranks = self.choice_ranks()
        if not self.definition.multi and choice in choice_ranks:
            return Decision(success=False, reason="Choice already taken.")

        if self.limit != "unlimited" and sum(choice_ranks.values()) >= self.limit:
            return Decision(
                success=False,
                reason=f"Choice {self._choice} of {self._feature.full_id} only accepts {self.limit} choices.",
            )

        self._record_choice(choice)
        return Decision(success=True, mutation_applied=True, reason="Choice applied.")

    def unchoose(self, choice: str) -> Decision:
        choice_ranks = self.choice_ranks()
        if choice not in choice_ranks:
            return Decision(success=False, reason="Choice not taken.")

        choices = self._feature.model.choices.get(self._choice) or []
        if choice_ranks[choice] <= 1:
            choices.remove(choice)
        else:
            expr = PropExpression.parse(choice)
            expr.value = choice_ranks[choice]
            choices.remove(repr(expr))
            expr.value -= 1
            choices.append(repr(expr))

        self._feature.model.choices[self._choice] = choices
        self._feature.reconcile()
        return Decision(success=True, mutation_applied=True, reason="Choice removed.")

    def _record_choice(self, choice: str) -> None:
        choice_ranks = self.choice_ranks()
        choices = self._feature.model.choices.get(self._choice) or []

        if choice in choice_ranks:
            # Already taken. If this is a multi-choice, we need to increment the value.
            if self.definition.multi:
                expr = PropExpression.parse(choice)
                expr.value = choice_ranks[choice]
                choices.remove(repr(expr))
                expr.value += 1
                choices.append(repr(expr))
            else:
                # Can't take a choice more than once!
                return Decision(success=False, reason="Choice already taken.")
        else:
            # Not yet taken. Add it to the list.
            choices.append(choice)

        self._feature.model.choices[self._choice] = choices
        self._feature.reconcile()

    def choice_ranks(self) -> dict[str, int]:
        ranks = {}
        if choices := self._feature.model.choices.get(self._choice):
            for choice in choices:
                expr = PropExpression.parse(choice)
                ranks[expr.full_id] = expr.value or 1
        return ranks

    def describe_choice(self, choice: str) -> str:
        expr = PropExpression.parse(choice)
        display_name = self._feature.character.display_name(expr.prop)
        if expr.option:
            display_name += f" [{expr.option}]"
        if expr.attribute:
            display_name += f" {self._feature.character.display_name(expr.attribute)}"
        if expr.value and expr.value > 1:
            display_name += f" x{expr.value}"
        return display_name

    @abstractmethod
    def update_propagation(
        self, grants: dict[str, int], discounts: dict[str, list[Discount]]
    ) -> None:
        """Apply the consequences of the provided choices."""
