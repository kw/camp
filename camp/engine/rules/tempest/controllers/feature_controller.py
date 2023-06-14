from __future__ import annotations

import math
from functools import cached_property
from typing import Iterable
from typing import Type

from camp.engine import utils
from camp.engine.rules import base_engine
from camp.engine.rules.base_models import Discount
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.decision import Decision

from .. import defs
from .. import models
from . import choice_controller

_MUST_BE_POSITIVE = Decision(success=False, reason="Value must be positive.")
_NO_RESPEND = Decision(success=False, reason="Respend not currently available.")
_NO_PURCHASE = Decision(success=False, reason="Feature cannot be purchased.")

_SUBFEATURE_TYPES: set[str] = {"subfeature", "innate", "archetype"}


class FeatureController(base_engine.BaseFeatureController):
    definition: defs.BaseFeatureDef
    character: base_engine.CharacterController
    model_type: Type[models.FeatureModel] = models.FeatureModel
    _effective_ranks: int | None

    # Subclasses can change the currency used, but CP is the default.
    # Note that no currency display will be shown if the feature has no cost model.
    currency: str | None = None

    def __init__(self, full_id: str, character: base_engine.CharacterController):
        super().__init__(full_id, character)
        self._effective_ranks = None

    @property
    def subfeatures(self) -> list[FeatureController]:
        return [
            fc for fc in self.taken_children if fc.feature_type in _SUBFEATURE_TYPES
        ]

    @property
    def internal(self) -> bool:
        return self.feature_type in _SUBFEATURE_TYPES

    @property
    def parent(self) -> FeatureController | None:
        if self.definition.parent is None:
            return None
        return self.character.controller(self.definition.parent)

    @property
    def formal_name(self) -> str:
        """Used in contexts where the feature's name should be listed along with its type and other qualifiers.

        This is typically used in places where features of different types and sources might be comingled in the same list,
        such as the list of internal features for a class.
        """
        return f"{self.display_name()} [{self.type_name}]"

    @property
    def type_name(self) -> str:
        base_name = self.character.display_name(self.feature_type)
        if self.parent:
            return f"{self.parent.display_name()} {base_name}"
        return base_name

    @property
    def feature_list_name(self) -> str:
        """Used in contexts where the type of the feature can be assumed, such as the main feature type lists on the character display.

        Subclasses may still add more details. For example, in a giant list of spells, it's likely still useful to note the class and tier.
        """
        if self.parent:
            return f"{super().feature_list_name} [{self.parent.display_name()}]"
        return f"{super().feature_list_name}"

    @property
    def taken_options(self) -> dict[str, int]:
        options = {}
        for controller in self.character.features.values():
            if controller.id == self.id and controller.option and controller.value > 0:
                options[controller.option] = controller.value
        return options

    @property
    def cost_def(self) -> defs.CostDef:
        if not hasattr(self.definition, "cost"):
            return None
        return self.definition.cost

    @property
    def cost(self) -> int:
        return self._cost_for(self.paid_ranks)

    @property
    def next_cost(self) -> int:
        return self._cost_for(self.paid_ranks + 1) - self._cost_for(self.paid_ranks)

    @property
    def currency_name(self) -> str | None:
        if self.currency:
            return self.character.display_name(self.currency)
        return None

    def purchase_cost_string(
        self, ranks: int = 1, cost: int | None = None
    ) -> str | None:
        if self.currency and self.cost_def:
            if cost is None:
                cost = self._cost_for(self.paid_ranks + ranks) - self._cost_for(
                    self.paid_ranks
                )
            return f"{cost} {self.currency_name}"
        return None

    @cached_property
    def model(self) -> models.FeatureModel:
        return self.character.model.features.get(self.full_id) or self.model_type()

    @property
    def free(self) -> bool:
        return self.model.plot_free

    @free.setter
    def free(self, value: bool) -> None:
        self.model.plot_free = value

    @property
    def purchased_ranks(self) -> int:
        return self.model.ranks

    @purchased_ranks.setter
    def purchased_ranks(self, value: int) -> None:
        if self.definition.ranks != "unlimited":
            self.model.ranks = min(value, self.definition.ranks)
        else:
            self.model.ranks = value
        self._link_model()

    def _link_model(self) -> None:
        model = self.model
        saved = self.full_id in self.character.model.features
        if model.should_keep() and not saved:
            self.character.model.features[self.full_id] = model
        elif not model.should_keep() and saved:
            del self.character.model.features[self.full_id]

    @property
    def explain(self) -> list[str]:
        """Returns a list of strings explaining details of the feature."""
        if self.model.plot_suppressed:
            return ["This feature was suppressed by a plot member."]

        if self.value <= 0:
            return []

        reasons = []
        if self.model.plot_added:
            reasons.append("This feature was added by a plot member.")
        if self.model.plot_free:
            reasons.append("This feature is free for plot reasons.")

        if self.definition.ranks == 1 and self.purchased_ranks == 1:
            reasons.append("You have taken this feature.")

        if self.definition.ranks != 1 and self.purchased_ranks > 0:
            reasons.append(
                f"You have taken {self.purchased_ranks} {self.rank_name(self.purchased_ranks)}."
            )

        if self.purchased_ranks > 0 and self.currency_name and self.cost > 0:
            reasons.append(
                f"You have spent {self.cost} {self.currency_name} on this feature."
            )

        if self._propagation_data:
            for source_id, data in self._propagation_data.items():
                source = self.character.display_name(source_id)
                if data.grants > 0:
                    source = self.character.display_name(source_id)
                    if data.grants == 1:
                        reasons.append(f"Granted by {source}.")
                    else:
                        reasons.append(
                            f"Granted {data.grants} {self.rank_name(data.grants)} from {source}."
                        )
                if data.discount:
                    for discount in data.discount:
                        reason = (
                            f"Discounted by {discount.discount} {self.currency_name}, "
                        )
                        if discount.minimum:
                            reason += f"minimum {discount.minimum}, "
                        if discount.ranks:
                            reason += f"up to {discount.ranks} {self.rank_name(discount.ranks)}, "
                        reason += f"via {source}."
                        reasons.append(reason)

        return reasons

    @property
    def granted_features(self) -> list[FeatureController]:
        """Returns a list of features granted by this feature."""
        controllers = (
            self.character.controller(id)
            for id, data in self._gather_propagation().items()
            if data.grants > 0
        )
        features = [f for f in controllers if isinstance(f, FeatureController)]
        features.sort(key=lambda f: f.full_id)
        return features

    @property
    def discounted_features(self) -> list[FeatureController]:
        """Returns a list of features discounted by this feature."""
        controllers = (
            self.character.controller(id)
            for id, data in self._gather_propagation().items()
            if data.discount
        )
        features = [f for f in controllers if isinstance(f, FeatureController)]
        features.sort(key=lambda f: f.full_id)
        return features

    @property
    def granted_ranks(self) -> int:
        return sum(d.grants for d in self._propagation_data.values())

    @property
    def discounts(self) -> Iterable[Discount]:
        for data in self._propagation_data.values():
            if data.discount:
                yield from data.discount

    @property
    def is_starting(self) -> bool:
        """Is this a 'starting' feature?

        This is only really defined for basic classes, which grant different benefits
        based on whether it's the first one taken. It may be relevant to subfeatures of
        those classes in certain circumstances, so we propagate it down.

        For other features, it doesn't matter. Return True for convenience.
        """
        if self.parent:
            return self.parent.is_starting
        return True

    @property
    def has_available_choices(self) -> bool:
        if choices := self.choices:
            for choice in choices.values():
                if choice.choices_remaining > 0:
                    return True
        return False

    @property
    def choices(self) -> dict[str, choice_controller.ChoiceController] | None:
        if not self.definition.choices or self.value < 1:
            return None
        choices = {
            key: choice_controller.make_controller(self, key)
            for key in self.definition.choices
        }
        if not self.is_starting:
            choices = {
                k: v for k, v in choices.items() if not v.definition.starting_class
            }
        return choices

    def choose(self, choice: str, selection: str) -> Decision:
        if controller := self.choices.get(choice):
            return controller.choose(selection)
        return Decision(success=False, reason=f"Unknown choice '{choice}'")

    def unchoose(self, choice: str, selection: str) -> Decision:
        if controller := self.choices.get(choice, None):
            return controller.unchoose(selection)
        return Decision(success=False, reason=f"Unknown choice '{choice}'")

    @property
    def paid_ranks(self) -> int:
        """Number of ranks purchased that actually need to be paid for with some currency.

        This is generally equal to `purchased_ranks`, but when grants push the total over the
        feature's maximum, these start to be refunded. They remain on the sheet in case the
        grants are revoked in the future due to an undo, a sellback, a class level swap, etc.
        """
        total = self.purchased_ranks + self.granted_ranks
        max_ranks = self.max_ranks
        if total <= max_ranks:
            return self.purchased_ranks
        # The feature is at maximum. Only pay for ranks that haven't been granted.
        # Note that the total grants could also exceed max_ranks. This is more likely
        # to happen with single-rank features like weapon proficiencies that a character
        # might receive from multiple classes.
        if self.granted_ranks < max_ranks:
            return max_ranks - self.granted_ranks
        return 0

    @property
    def value(self) -> int:
        if self.option_def and not self.option:
            # This is an aggregate controller for the feature.
            # Sum any ranks the character has in instances of it.
            total: int = 0
            for feat, controller in self.character.features.items():
                if feat.startswith(f"{self.id}+"):
                    total += controller.value
            return total
        if self._effective_ranks is None:
            self.reconcile()
        if self.model.plot_suppressed:
            return 0
        return self._effective_ranks

    @property
    def max_value(self) -> int:
        if self.option_def and not self.option:
            # This is an aggregate controller for the feature.
            # Return the value of the highest instance.
            current: int = 0
            for feat, controller in self.character.features.items():
                if feat.startswith(f"{self.id}+"):
                    new_value = controller.value
                    if new_value > current:
                        current = new_value
            return current
        return super().max_value

    @property
    def choice_defs(self) -> dict[str, defs.ChoiceDef]:
        """Map of choice IDs to definitions available for this feature."""
        return self.definition.choices or {}

    @property
    def notes(self) -> str | None:
        return self.model.notes

    @notes.setter
    def notes(self, value: str | None) -> None:
        self.model.notes = value

    @property
    def purchaseable_ranks(self) -> int:
        if self.option_def and not self.option:
            return self.max_ranks
        return max(self.max_ranks - self.value, 0)

    @property
    def meets_requirements(self) -> Decision:
        return self.character.meets_requirements(self.definition.requires)

    def _link_to_character(self):
        if self.full_id not in self.character.features:
            self.character.features[self.full_id] = self

    def can_increase(self, value: int = 1) -> Decision:
        if value <= 0:
            return _MUST_BE_POSITIVE
        purchaseable = self.purchaseable_ranks
        current = self.value
        if purchaseable <= 0:
            return Decision(success=False)
        # Is the purchase within defined range?
        if value > purchaseable:
            return Decision(
                success=False,
                reason=f"Max is {self.definition.ranks}, so can't increase to {current + value}",
                amount=purchaseable,
            )
        # Does the character meet the prerequisites?
        if not (rd := self.character.meets_requirements(self.definition.requires)):
            return rd
        # Is this an option skill without an option specified?
        if (
            self.option_def
            and self.option
            and not self.definition.option.freeform
            and self.purchased_ranks == 0
        ):
            # The player is trying to buy a new option. Verify that it's legal.
            options_available = self.character.options_values_for_feature(
                self.id, exclude_taken=True
            )
            if self.option not in options_available:
                return Decision(
                    success=False,
                    reason=f"'{self.option}' not a valid option for {self.id}",
                )
        # Is this a non-option skill and an option was specified anyway?
        if not self.option_def and self.option:
            return Decision(
                success=False, reason=f"Feature {self.id} does not accept options."
            )
        # Is this a skill with a cost that must be paid? If so, can we pay it?
        if not (rd := self.can_afford(value)):
            return rd

        # Checks for option logic.
        if self.option_def:
            # If this is an option feature and the option was specified,
            # this is either a new or existing option. If it's existing, that's fine.
            # If it's new, we need to make sure the character has enough options left.
            if self.option:
                if self.value > 0:
                    # This isn't new, so we don't need to check if we can add a new option.
                    return Decision.OK
                if not self.can_take_new_option:
                    # This is a new option, but we're at max. Report negative.
                    return Decision(
                        success=False,
                        reason=f"Can't take new option for {self.id} because the maximum number of options has been reached.",
                    )
            if not self.option:
                # Just checking whether the option template is available.
                if self.can_take_new_option:
                    # If this is a non-freeform option, are there any valid options left?
                    if (
                        not self.definition.option.freeform
                        and not self.available_options
                    ):
                        return Decision.NO
                    return Decision.NEEDS_OPTION
                else:
                    return Decision.NO
        return Decision.OK

    def can_afford(self, value: int = 1) -> Decision:
        available = self._currency_balance()
        if available is None:
            return _NO_PURCHASE
        currency_delta = self._cost_for(self.paid_ranks + value) - self.cost
        if available < currency_delta:
            return Decision(
                success=False,
                need_currency={self.currency: currency_delta},
                reason=f"Need {currency_delta} {self.currency_name} to purchase, but only have {available}",
                amount=self._max_rank_increase(available),
            )
        return Decision.OK

    def can_decrease(self, value: int = 1) -> Decision:
        if not self.character.can_respend:
            return _NO_RESPEND
        if value < 1:
            return _MUST_BE_POSITIVE
        purchases = self.purchased_ranks
        if value > purchases:
            return Decision(
                success=False,
                reason=f"Can't sell back {value} ranks when you've only purchased {purchases} ranks.",
                amount=(value - purchases),
            )
        return Decision.OK

    def increase(self, value: int) -> Decision:
        if not (rd := self.can_increase(value)):
            return rd
        if rd.needs_option:
            return Decision.NEEDS_OPTION_FAIL
        self.purchased_ranks += value
        self.reconcile()
        return Decision(success=True, amount=self.value, mutation_applied=True)

    def decrease(self, value: int) -> Decision:
        if not (rd := self.can_decrease(value)):
            return rd
        self.purchased_ranks -= value
        self.reconcile()
        return Decision.OK

    def reconcile(self) -> None:
        """If this controller's value has been updated (or on an initial pass on character load), update grants.

        Grants represent any feature (or feature ranks) gained simply by possessing this feature (or a number of ranks of it).
        All features in this model have a `grants` field in their definition that specify one or more features to grant one or
        more ranks of, and this will be processed whenever any ranks of this feature are possessed.

        Subclasses may have more specific grants. For example, a character class may automatically grant certain features at specific levels.
        """
        self._effective_ranks = min(
            self.granted_ranks + self.purchased_ranks, self.max_ranks
        )
        self._link_to_character()
        self._update_choices()
        self._link_model()
        self._perform_propagation()

    def _update_choices(self) -> None:
        if self.choice_defs:
            # Create choice structures if not already created.
            if self.model.choices is None:
                self.model.choices = {}
            for choice_id in self.choice_defs:
                if self.value > 0 and choice_id not in self.model.choices:
                    self.model.choices[choice_id] = []

    def _perform_propagation(self) -> None:
        props = self._gather_propagation()
        for id, data in props.items():
            if controller := self.character.controller(id):
                controller.propagate(data)

    def extra_grants(self) -> dict[str, int]:
        """Return any extra grants that should be applied for this feature.

        This is used for features that grant other features, such as a class granting a skill.
        """
        return {}

    def _gather_propagation(self) -> dict[str, base_engine.PropagationData]:
        # Basic grants that are always provided by the feature.
        if grant_def := self.definition.grants:
            grants = self._gather_grants(grant_def)
        else:
            grants = {}
        # Handle the rank grant table, if present. This table is keyed by the number of ranks
        # purchased in the feature, and the value is a dict of grants to apply. You get all
        # grants on the table up to your current rank level.
        if self.definition.rank_grants:
            for rank in range(self.value + 1):
                if grant := self.definition.rank_grants.get(rank):
                    grants.update(self._gather_grants(grant))
        # Subclasses might have other grants that the produce. Add them in.
        grants.update(self.extra_grants())

        # Collect discounts, if present.
        if discount_def := getattr(self.definition, "discounts", None):
            discounts = self._gather_discounts(discount_def)
        else:
            discounts = {}
        # Choices may also affect grants/discounts.
        if self.choices:
            for choice in self.choices.values():
                choice.update_propagation(grants, discounts)
        # Now that we have all the grants and discounts, create the propagation data.
        props: dict[str, base_engine.PropagationData] = {}
        all_keys = set(grants.keys()).union(discounts.keys())
        for expr in all_keys:
            data = props[expr] = base_engine.PropagationData(
                source=self.full_id, target=PropExpression.parse(expr)
            )
            if self.value > 0:
                if g := grants.get(expr):
                    data.grants = g
                if d := discounts.get(expr):
                    data.discount = d
        return props

    def _gather_grants(self, grants: defs.Grantable) -> dict[str, int]:
        grant_map: dict[str, int] = {}
        if not grants:
            return grant_map
        elif isinstance(grants, str):
            expr = PropExpression.parse(grants)
            value = expr.value or 1
            grant_map[expr.full_id] = value
        elif isinstance(grants, list):
            for grant in grants:
                grant_map.update(self._gather_grants(grant))
        elif isinstance(grants, dict):
            grant_map.update(grants)
        elif isinstance(grants, defs.GrantDef):
            grant_value = grants.value
            self_value = self.value
            if isinstance(grant_value, (list, dict)):
                grant_value = utils.table_lookup(grant_value, self_value)
            if grants.per_rank:
                grant_value *= self_value
            grant_map[grants.id] = grant_value
        else:
            raise NotImplementedError(f"Unexpected grant value: {grants}")
        return grant_map

    def _gather_discounts(self, discounts: defs.Discounts) -> dict[str, list[Discount]]:
        discount_map: dict[str, list[Discount]] = {}
        if not discounts:
            return discount_map
        elif isinstance(discounts, dict):
            for key, value in discounts.items():
                if key not in discount_map:
                    discount_map[key] = []
                discount_map[key].append(Discount.cast(value))
            return discount_map
        else:
            raise NotImplementedError(f"Unexpected discount value: {discounts}")

    def _cost_for(self, ranks: int) -> int:
        """Returns the cost for the number of ranks, typically in CP.

        This tries to take into account any active discounts applied to this feature.

        This does not handle awards.
        """
        if self.free:
            return 0
        cd = self.cost_def
        # First account for "normal" purchased ranks
        if cd is None:
            return 0
        elif isinstance(cd, int):
            # Most powers use a simple "N CP per rank" cost model
            rank_costs = [cd] * ranks
        elif isinstance(cd, defs.CostByRank):
            # But some have to be difficult and specify varying costs per rank.
            rank_costs = cd.rank_costs(ranks)
        else:
            raise NotImplementedError(f"Don't know how to compute cost with {cd}")
        # Apply per-rank discounts.
        for discount in self.discounts:
            ranks = len(rank_costs)
            if discount.ranks and discount.ranks < ranks:
                ranks = discount.ranks
            # For discounts that only affect a limited number of ranks, start from the top,
            # since later ranks are normally more expensive (if they vary at all).
            for r in range(ranks):
                i = -1 - r
                # Don't try to apply the discount if the rank cost is
                # already 0. This means if two discounts apply and one of them
                # has minimum=0, it will "stick" and the other discount won't pop
                # it back up to 1.
                if rank_costs[i] > 0:
                    rank_costs[i] -= discount.discount
                    if rank_costs[i] < discount.minimum:
                        rank_costs[i] = discount.minimum
        return sum(rank_costs)

    def _max_rank_increase(self, available: int = -1) -> int:
        if available < 0:
            available = self._currency_balance()
        available_ranks = self.purchaseable_ranks
        current_cost = self.cost
        if available_ranks < 1:
            return 0
        match cd := self.cost_def:
            case int():
                # Relatively trivial case
                return min(available_ranks, math.floor(available / cd))
            case defs.CostByRank():
                while available_ranks > 0:
                    cp_delta = (
                        self._cost_for(self.paid_ranks + available_ranks) - current_cost
                    )
                    if cp_delta <= available:
                        return available_ranks
                    available_ranks -= 1
                return 0
        raise NotImplementedError(f"Don't know how to compute cost with {cd}")

    def _currency_balance(self) -> int | None:
        match self.currency:
            case "cp":
                return self.character.cp.value
            case None:
                return None
            case _:
                return 0

    @property
    def explain_type_group(self) -> str | None:
        if (balance := self._currency_balance()) is not None:
            return f"{balance} {self.currency_name} available"
        return None

    @property
    def explain_category_group(self) -> str | None:
        return None

    @property
    def explain_list(self) -> list[str]:
        return []


class SkillController(FeatureController):
    definition: defs.SkillDef
    currency: str = "cp"


class PerkController(FeatureController):
    definition: defs.PerkDef
    currency: str = "cp"
