from __future__ import annotations

from functools import cached_property
from typing import Literal
from typing import cast

from camp.engine.rules import base_engine
from camp.engine.rules.base_models import Discount

from ...decision import Decision
from .. import defs
from . import feature_controller

# TODO: When too many choices have been taken (usually because the character has lost points in the feature),
# the player should be prompted to remove choices.


class BaseFeatureChoice(base_engine.ChoiceController):
    _feature: feature_controller.FeatureController
    _choice: str

    def __init__(self, feature: feature_controller.FeatureController, choice_id: str):
        self._feature = feature
        self._choice = choice_id

    @cached_property
    def definition(self) -> defs.ChoiceDef:
        return cast(
            feature_controller.FeatureController, self._feature.definition
        ).choices[self._choice]

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

    def taken_choices(self) -> dict[str, str]:
        taken = {}
        if choices := self._feature.model.choices.get(self._choice):
            for choice in choices:
                taken[choice] = self._feature.character.display_name(choice)
        return taken

    def _matching_features(self):
        return {
            choice
            for choice in self._feature.character.ruleset.features
            if self._matches(choice)
        }

    def _record_choice(self, choice: str) -> None:
        choices = self._feature.model.choices.get(self._choice) or []
        choices.append(choice)
        self._feature.model.choices[self._choice] = choices
        self._feature.reconcile()

    def choose(self, choice: str) -> Decision:
        taken = self.taken_choices()
        if choice in taken:
            return Decision(success=False, reason="Choice already taken.")
        if self.limit != "unlimited" and len(taken) >= self.limit:
            return Decision(
                success=False,
                reason=f"Choice {self._choice} of {self._feature.full_id} only accepts {self.limit} choices.",
            )

        if not self._matches(choice):
            return Decision(
                success=False,
                reason=f"`{choice}` does not match choice definition for {self._feature.full_id}/{self._choice}",
            )

        self._record_choice(choice)
        return Decision(success=True, mutation_applied=True, reason="Choice applied.")

    def _matches(self, choice: str) -> bool:
        if feat := self._feature.character.feature_def(choice):
            return self.definition.matcher.matches(feat)
        return False

    def unchoose(self, feature: str) -> Decision:
        taken = self.taken_choices()
        if feature not in taken:
            return Decision(success=False, reason="Choice not taken.")

        choices = self._feature.model.choices.get(self._choice) or []
        choices.remove(feature)
        self._feature.model.choices[self._choice] = choices
        self._feature.reconcile()
        return Decision(success=True, mutation_applied=True, reason="Choice removed.")

    def removable_choices(self) -> set[str]:
        # TODO: Prevent choices from being removed when the character is not in "free edit" mode.
        # There may be other circumstances when a choice can or can't be removed.
        # TODO: Allow choices to be removed when the character has more choices than they are allowed.
        return self.taken_choices()


class GrantChoice(BaseFeatureChoice):
    def available_choices(self) -> dict[str, str]:
        # Already taken too many?
        if self.choices_remaining <= 0:
            return {}

        feats = self._matching_features()
        feats -= set(self.taken_choices().keys())

        choices = {}
        for expr in sorted(feats):
            feat = self._feature.character.feature_controller(expr)
            short = feat.short_description
            descr = getattr(feat, "formal_name", feat.display_name())
            if not feat.possible_ranks:
                descr = f"{descr} (Already at Max)"
            elif short:
                descr = f"{descr}: {short}"

            choices[expr] = descr
        return choices

    def update_propagation(
        self, grants: dict[str, int], discounts: dict[str, list[Discount]]
    ) -> None:
        for choice in self.taken_choices():
            if choice not in grants:
                grants[choice] = 0
            grants[choice] += 1


class PatronChoice(BaseFeatureChoice):
    def available_choices(self) -> dict[str, str]:
        # Already taken too many?
        if self.choices_remaining <= 0:
            return {}

        feats = self._matching_features()
        feats -= set(self.taken_choices().keys())

        choices = {}
        for expr in sorted(feats):
            feat = self._feature.character.feature_controller(expr)
            short = feat.short_description
            name = getattr(feat, "formal_name", feat.display_name())
            choices[expr] = f"{name}: {short}" if short else name
        return choices

    def update_propagation(
        self, grants: dict[str, int], discounts: dict[str, list[Discount]]
    ) -> None:
        for choice in self.taken_choices():
            if self._feature.model.plot_suppressed:
                # TODO(#38): Propagate suppression to chosen features.
                continue
            if choice not in discounts:
                discounts[choice] = []
            discounts[choice].append(Discount(discount=1, minimum=1, ranks=1))


def make_controller(
    feature: feature_controller.FeatureController, choice_id: str
) -> base_engine.ChoiceController:
    """Factory function for custom choice controllers."""
    choice_def = feature.definition.choices[choice_id]
    match choice_def.controller:
        case "sphere-bonus":
            from .custom import sphere_bonus_choice

            return sphere_bonus_choice.SphereBonusChoice(feature, choice_id)
        case "patron":
            return PatronChoice(feature, choice_id)
        case None:
            return GrantChoice(feature, choice_id)
        case _:
            raise ValueError(f"Unknown choice controller '{choice_def.controller}'")
