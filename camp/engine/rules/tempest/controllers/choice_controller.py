from __future__ import annotations

from functools import cached_property
from typing import Literal
from typing import cast

from ...decision import Decision
from .. import defs
from . import feature_controller


class ChoiceController:
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
        return self.definition.limit

    @property
    def choices_remaining(self) -> int:
        if self.limit == "unlimited":
            return 999
        return self.limit - len(self.taken_choices())

    def valid_choices(self) -> dict[str, str]:
        taken = self.taken_choices()
        character = self._feature.character

        # Already taken too many?
        if self.limit != "unlimited" and len(taken) >= self.limit:
            return set()

        matcher = self.definition.matcher
        if matcher:
            feats = {
                id
                for id, feat in character.ruleset.features.items()
                if matcher.matches(feat)
            }
        else:
            # No matcher, no matches.
            return set()

        feats -= taken
        choices = {}
        for expr in sorted(feats):
            feat = character.feature_controller(expr)
            short = feat.short_description
            if short:
                choices[expr] = f"{feat.display_name()}: {short}"
            else:
                choices[expr] = feat.display_name()
        return choices

    def choose(self, feature: str) -> Decision:
        taken = self.taken_choices()
        if feature in taken:
            return Decision(success=False, reason="Choice already taken.")
        if self.limit != "unlimited" and len(taken) >= self.limit:
            return Decision(
                success=False,
                reason=f"Choice {self._choice} of {self._feature.full_id} only accepts {self.limit} choices.",
            )

        feature_def = self._feature.character.feature_def(feature)
        if not feature_def:
            return Decision(
                success=False, reason=f"Feature definition not found for {feature}."
            )

        matcher = self.definition.matcher
        if not matcher or not matcher.matches(feature_def):
            return Decision(
                success=False,
                reason=f"`{feature}` does not match choice definition for {self._feature.full_id}/{self._choice}",
            )

        character = self._feature.character
        feat_controller = character.feature_controller(feature)

        # The choice is technically valid, but can the character actually choose it?
        # This depends a bit on the type of choice. If the choice grants ranks, the character may or may not have to
        # meet some or all of its requirements, which is a bit complex.
        # If the choice just applies a discount, like with Patron, all we care about is whether the character currently
        # has currently paid for or can currently buy the feature (ignoring the question of whether the character can afford it).

        # If you've bought it (and this is a discount), can buy it now, or _could_ buy it if you had the currency, good enough.
        # Features that do not have a currency cost are always valid.
        rd = feat_controller.can_increase()
        if (
            (self.definition.discount and feat_controller.paid_ranks > 0)
            or rd
            or rd.need_currency
            or feat_controller.currency is None
        ):
            choices = self._feature.model.choices.get(self._choice) or []
            choices.append(feature)
            self._feature.model.choices[self._choice] = choices
            self._feature.reconcile()
            return Decision(
                success=True, mutation_applied=True, reason="Choice applied."
            )

        # If the decision was negative report the increase decision back. It might have useful info.
        if not rd:
            return rd
        # Otherwise, just return a generic failure.
        return Decision(success=False, reason="Choice could not be applied.")

    def unchoose(self, feature: str) -> Decision:
        taken = self.taken_choices()
        if feature not in taken:
            return Decision(success=False, reason="Choice not taken.")

        choices = self._feature.model.choices.get(self._choice) or []
        choices.remove(feature)
        self._feature.model.choices[self._choice] = choices
        self._feature.reconcile()
        return Decision(success=True, mutation_applied=True, reason="Choice removed.")

    def taken_choices(self) -> set[str]:
        if choices := self._feature.model.choices.get(self._choice):
            return set(choices)
        return set()

    def removable_choices(self) -> set[str]:
        # TODO: Prevent choices from being removed when the character is not in "free edit" mode.
        # There may be other circumstances when a choice can or can't be removed.
        return self.taken_choices()

    def taken_features(self) -> list[feature_controller.FeatureController]:
        features = [
            self._feature.character.feature_controller(id)
            for id in self.taken_choices()
        ]
        features.sort(key=lambda f: f.display_name())
        return features

    def available_features(self) -> list[feature_controller.FeatureController]:
        features = [
            self._feature.character.feature_controller(id)
            for id in self.valid_choices()
        ]
        features.sort(key=lambda f: f.full_id)
        return features

    def update_propagation(
        self, grants: dict[str, int], discounts: dict[str, list[defs.Discount]]
    ) -> None:
        for choice in self.taken_choices():
            if self.definition.discount:
                if choice not in discounts:
                    discounts[choice] = []
                discounts[choice].append(defs.Discount.cast(self.definition.discount))
            else:
                if choice not in grants:
                    grants[choice] = 0
                grants[choice] += 1
