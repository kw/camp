from __future__ import annotations

from functools import cached_property
from typing import Literal
from typing import cast

from camp.engine.rules import base_engine
from camp.engine.rules.base_models import Discount
from camp.engine.rules.tempest import engine

from ...decision import Decision
from .. import defs

# TODO: When too many choices have been taken (usually because the character has lost points in the feature),
# the player should be prompted to remove choices.


class BaseFeatureChoice(engine.ChoiceController):
    _feature: base_engine.BaseFeatureController
    _choice: str

    def __init__(self, feature: base_engine.BaseFeatureController, choice_id: str):
        self._feature = feature
        self._choice = choice_id

    @cached_property
    def definition(self) -> defs.ChoiceDef:
        return cast(defs.BaseFeatureDef, self._feature.definition).choices[self._choice]

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

    def choose(self, choice: str) -> Decision:
        if not self._matches(choice):
            return Decision(
                success=False,
                reason=f"`{choice}` does not match choice definition for {self._feature.full_id}/{self._choice}",
            )
        return super().choose(choice)

    def _matching_features(self):
        return {
            choice
            for choice in self._feature.character.ruleset.features
            if self._matches(choice)
        }

    def _matches(self, choice: str) -> bool:
        if feat := self._feature.character.feature_def(choice):
            return self.definition.matcher.matches(feat)
        return False

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


def make_controller(
    feature: base_engine.BaseFeatureController, choice_id: str
) -> engine.ChoiceController:
    """Factory function for custom choice controllers."""
    choice_def = cast(defs.BaseFeatureDef, feature.definition).choices[choice_id]
    match choice_def.controller:
        case "sphere-grant":
            from . import sphere_choice

            return sphere_choice.SphereGrantChoice(feature, choice_id)
        case "sphere-bonus":
            from . import sphere_choice

            return sphere_choice.SphereBonusChoice(feature, choice_id)
        case "patron":
            from . import patron_choice

            return patron_choice.PatronChoice(feature, choice_id)
        case None:
            return GrantChoice(feature, choice_id)
        case _:
            raise ValueError(f"Unknown choice controller '{choice_def.controller}'")
