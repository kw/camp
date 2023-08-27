from __future__ import annotations

import math
from functools import cached_property
from typing import Iterable
from typing import Type

from camp.engine import utils
from camp.engine.rules import base_engine
from camp.engine.rules.base_models import Discount
from camp.engine.rules.base_models import Issue
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.decision import Decision

from .. import defs
from .. import models
from . import choice_controller

_MUST_BE_POSITIVE = Decision(success=False, reason="Value must be positive.")
_NO_RESPEND = Decision(success=False, reason="Respend not currently available.")
_NO_PURCHASE = Decision(success=False, reason="Feature cannot be purchased.")

_SUBFEATURE_TYPES: set[str] = {
    "subfeature",
    "innate",
    "archetype",
    "inheritance",
    "devotion",
    "subbreed",
    "breedchallenge",
    "breedadvantage",
}
_OPTION_BONUS = "__option__"


class FeatureController(base_engine.BaseFeatureController):
    definition: defs.BaseFeatureDef
    character: base_engine.CharacterController
    model_type: Type[models.FeatureModel] = models.FeatureModel
    can_buy_without_parent: bool = False
    _effective_ranks: int | None

    # Subclasses can change the currency used, but CP is the default.
    # Note that no currency display will be shown if the feature has no cost model.
    currency: str | None = None

    def __init__(self, full_id: str, character: base_engine.CharacterController):
        super().__init__(full_id, character)
        self._effective_ranks = None
        assert isinstance(
            self.definition, (expected_type := self._definition_type())
        ), f"Expected {self.definition} to be of type {expected_type} but was {type(self.definition)}"  # nosec assert_used

    @classmethod
    def _definition_type(cls) -> Type[defs.BaseFeatureDef]:
        annotation = cls.__annotations__.get("definition")
        defs_name, typename = annotation.split(".")
        if defs_name != "defs":
            # Let's not think too hard about this if we don't recognize the defs module.
            return defs.BaseFeatureDef
        return getattr(defs, typename)

    @property
    def subfeatures(self) -> list[FeatureController]:
        return [
            fc for fc in self.taken_children if fc.feature_type in _SUBFEATURE_TYPES
        ]

    @property
    def subfeatures_available(self) -> list[FeatureController]:
        return [
            fc
            for fc in self.children
            if fc.feature_type in _SUBFEATURE_TYPES and fc.can_increase()
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

    @cached_property
    def tag_names(self) -> list[str]:
        names = []
        for tag in self.tags:
            tag_name = self.character.ruleset.tags.get(tag, None)
            if tag_name:
                names.append(tag_name)
        names.sort()
        return names

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
        return {
            option: controller.value
            for option, controller in self.option_controllers.items()
        }

    @property
    def cost_def(self) -> defs.CostDef:
        return getattr(self.definition, "cost", None)

    @property
    def cost(self) -> int:
        return self._cost_for(self.paid_ranks, self.bonus)

    @property
    def cost_string(self) -> str | None:
        return self.purchase_cost_string(cost=self.cost)

    @property
    def next_cost(self) -> int:
        if self.unused_bonus > 0:
            return 0
        grants = 0 if self.is_option_template else self.bonus
        return self._cost_for(self.paid_ranks + 1, grants) - self._cost_for(
            self.paid_ranks, grants
        )

    @property
    def currency_name(self) -> str | None:
        if self.currency:
            return self.character.display_name(self.currency, use_abbrev=True)
        return None

    def purchase_cost_string(
        self, ranks: int = 1, cost: int | None = None
    ) -> str | None:
        if self.currency and self.cost_def is not None:
            if cost is None:
                if self.is_option_template:
                    grants = 0
                else:
                    grants = self.bonus
                ranks = max(0, ranks - self.unused_bonus)
                cost = self._cost_for(self.paid_ranks + ranks, grants) - self._cost_for(
                    self.paid_ranks, grants
                )
            if cost >= 0:
                return f"{cost} {self.currency_name}"
            return f"+{abs(cost)} {self.currency_name}"
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
                        reasons.append(f"Granted by [{source}](../{source_id}).")
                    else:
                        reasons.append(
                            f"Granted {data.grants} {self.rank_name(data.grants)} from [{source}](../{source_id})."
                        )
                if data.discount:
                    for discount in data.discount:
                        reason = (
                            f"Discounted by {discount.discount} {self.currency_name}, "
                        )
                        if discount.ranks:
                            reason += f"up to {discount.ranks} {self.rank_name(discount.ranks)}, "
                        reason += f"via [{source}](../{source_id})."
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
    def badges(self) -> list[tuple[str, str]] | None:
        badges = super().badges
        if self.unused_bonus:
            badges.append(("success", "Bonus Available"))
        elif (
            self.supports_child_purchases
            and (
                self.child_purchase_remaining is None
                or self.child_purchase_remaining > 0
            )
            and self.subfeatures_available
        ):
            badges.append(("primary", "Purchases Available"))
        elif self.has_available_choices:
            badges.append(("primary", "Choices Available"))
        return badges

    @property
    def has_available_choices(self) -> bool:
        if choices := self.choices:
            for choice in choices.values():
                if choice.choices_remaining > 0 and choice.advertise:
                    return True
        return False

    @property
    def choices(self) -> dict[str, choice_controller.ChoiceController] | None:
        if self.definition.choices and self.value > 0:
            choices = {
                key: choice_controller.make_controller(self, key)
                for key in self.definition.choices
            }
            if not self.is_starting:
                choices = {
                    k: v for k, v in choices.items() if not v.definition.starting_class
                }
        else:
            choices = {}
        if self.option_def and not self.option and self.bonus:
            choices[_OPTION_BONUS] = choice_controller.OptionBonusRouter(
                self, _OPTION_BONUS
            )
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
    def value(self) -> int:
        if self.option_def and not self.option:
            # This is an aggregate controller for the feature.
            # Sum any ranks the character has in instances of it.
            total: int = 0
            for controller in self.option_controllers.values():
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
            for controller in self.option_controllers.values():
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

    def _link_to_character(self):
        if self.full_id not in self.character.features:
            self.character.features[self.full_id] = self

    @property
    def supports_child_purchases(self) -> bool:
        return self.definition.child_purchase is not None

    @property
    def child_purchase_limit(self) -> int | None:
        if not self.definition.child_purchase:
            return None
        if basis_id := self.definition.child_purchase.basis:
            basis = self.character.get(basis_id)
        else:
            basis = self.value

        if table := self.definition.child_purchase.limit:
            limit = table.evaluate(basis)
        else:
            limit = basis
        return limit

    @property
    def child_purchase_count(self) -> int:
        return sum(c.purchased_ranks for c in self.children)

    @property
    def child_purchase_remaining(self) -> int | None:
        if (limit := self.child_purchase_limit) is not None:
            return limit - self.child_purchase_count
        return None

    def can_increase(self, value: int = 1) -> Decision:
        if value <= 0:
            return _MUST_BE_POSITIVE
        purchaseable = self.purchaseable_ranks
        current = self.value
        if purchaseable <= 0:
            return Decision(success=False)
        # If the parent feature has purchase limits for children, enforce it.
        if self.parent and self.parent.supports_child_purchases:
            if (remaining := self.parent.child_purchase_remaining) is not None:
                if remaining < value:
                    return Decision(
                        success=False,
                        reason=f"Can't increase {self.display_name()} by {value} because {self.parent.display_name()}'s current limit is {remaining}.",
                        amount=max(remaining - value, 0),
                    )
        # Is the purchase within defined range?
        if value > purchaseable:
            return Decision(
                success=False,
                reason=f"Max is {self.definition.ranks}, so can't increase to {current + value}",
                amount=purchaseable,
            )
        # Does the character meet the prerequisites?
        if not (rd := self.meets_requirements):
            return rd
        # Is this an option skill without an option specified?
        if (
            self.option_def
            and self.expr.option
            and not self.definition.option.freeform
            and self.purchased_ranks == 0
        ):
            # The player is trying to buy a new option. Verify that it's legal.
            options_available = self.character.options_values_for_feature(
                self.id, exclude_taken=True
            )
            if self.expr.option not in options_available:
                return Decision(
                    success=False,
                    reason=f"'{self.expr.option}' not a valid option for {self.id}",
                )
        # Is this a non-option skill and an option was specified anyway?
        if not self.option_def and self.expr.option:
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
        grants = 0 if self.is_option_template else self.bonus
        currency_delta = self._cost_for(self.paid_ranks + value, grants) - self.cost
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
        # There's no use in selling back ranks if the feature is already fully refunded.
        if self.bonus >= self.max_ranks:
            return Decision(success=False, reason="Feature is already fully refunded.")
        return Decision.OK

    def increase(self, value: int) -> Decision:
        if (oc := self.option_parent) and oc.unused_bonus:
            if oc.model.choices is None:
                oc.model.choices = {}
            oc.model.choices[_OPTION_BONUS] = [self.full_id]
            oc.reconcile()
            return Decision(success=True, amount=1, mutation_applied=True)
        if not (rd := self.can_increase(value)):
            return rd
        if rd.needs_option:
            return Decision.NEEDS_OPTION_FAIL
        self.purchased_ranks += value
        self.reconcile()

        return Decision(success=True, amount=self.value, mutation_applied=True)

    @property
    def option_parent(self) -> FeatureController | None:
        if self.option_def and self.option:
            return self.character.controller(self.id)
        return None

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
        self._effective_ranks = min(self.bonus + self.purchased_ranks, self.max_ranks)
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

    @property
    def unused_bonus(self) -> int:
        """Returns the number of bonus ranks that can be used to get free options."""
        if self.bonus and self.option_def and not self.option:
            if (choices := self.choices) and (
                option_bonus := choices.get(_OPTION_BONUS)
            ):
                return option_bonus.choices_remaining
            return self.bonus
        return 0

    @property
    def should_show_in_list(self) -> bool:
        if super().should_show_in_list:
            return True
        if self.is_option_template and self.unused_bonus and self.can_take_new_option:
            return True
        return False

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
        # Handle conditional grants (grant_if).
        if self.definition.grant_if:
            for grant, requires in self.definition.grant_if.items():
                if self.character.meets_requirements(requires, self.full_id):
                    grants.update(self._gather_grants(grant))
        # Subclasses might have other grants that the produce. Add them in.
        grants.update(self.extra_grants())

        # Collect discounts, if present.
        if discount_def := getattr(self.definition, "discounts", None):
            discounts = self._gather_discounts(discount_def)
        else:
            discounts = {}
        # Choices may also affect grants/discounts.
        if choices := self.choices:
            for choice in choices.values():
                choice.update_propagation(grants, discounts)
        # Now that we have all the grants and discounts, create the propagation data.
        props: dict[str, base_engine.PropagationData] = {}
        all_keys = set(grants.keys()).union(discounts.keys())
        for expr in all_keys:
            data = props[expr] = base_engine.PropagationData(
                source=self.full_id, target=PropExpression.parse(expr)
            )
            if self.value > 0 or self.is_option_template:
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
            for feature_id, value in discounts.items():
                value = Discount.cast(value)
                if feature_id not in discount_map:
                    discount_map[feature_id] = []
                discount_map[feature_id].append(value)
                if feature := self.character.feature_controller(feature_id):
                    feature: FeatureController
                    if feature.is_option_template:
                        for option in feature.option_controllers.values():
                            if option.full_id not in discount_map:
                                discount_map[option.full_id] = []
                            discount_map[option.full_id].append(value)
            return discount_map
        else:
            raise NotImplementedError(f"Unexpected discount value: {discounts}")

    def _cost_for(self, purchased_ranks: int, granted_ranks: int = 0) -> int:
        """Returns the cost for the number of ranks, typically in CP.

        This tries to take into account any active discounts applied to this feature.
        """
        if self.free or not (cd := self.cost_def):
            return 0

        max_ranks = self.max_ranks
        effective_ranks = min(max_ranks, purchased_ranks + granted_ranks)
        grants_used = min(max_ranks, granted_ranks)
        paid_ranks = effective_ranks - grants_used

        # Compute the CP cost of the paid ranks. This is generally simple
        # multiplication, but some features have variable-cost ranks. However,
        # in all of those cases the "cheapest" ranks are the first ones. So,
        # we'll always assume that purchased ranks are "first" and granted ranks
        # are "last" for ordering purposes.
        if isinstance(cd, int):
            # Most powers use a simple "N CP per rank" cost model
            paid_cost = cd * paid_ranks
            potential_cost = cd * grants_used
            refund_value = cd
        elif isinstance(cd, defs.CostByRank):
            # But some have to be difficult and specify varying costs per rank.
            paid_cost = sum(cd.rank_costs(paid_ranks))
            potential_cost = sum(cd.rank_costs(effective_ranks)) - paid_cost
            refund_value = cd.single_rank_cost(max_ranks)
        else:
            raise NotImplementedError(f"Don't know how to compute cost with {cd}")

        # Apply discounts. Discounts apply whether the ranks are actually paid for or not.
        # The paid cost can't be reduced to below 1 per paid rank.
        # Granted ranks produce a rebate if discounted. The rebate value can potentially grant
        # nearly all of the "potential cost" of the granted ranks (all but 1 of the cost per rank).
        discount_total = 0
        rebate_total = 0
        potential_discount = max(paid_cost - paid_ranks, 0)
        potential_rebate = max(potential_cost - grants_used, 0)
        for discount in self.discounts:
            discountable_ranks = discount.ranks or effective_ranks
            discount_total += discount.discount * min(paid_ranks, discountable_ranks)
            rebate_total += discount.discount * min(grants_used, discountable_ranks)
        applied_discount = min(discount_total, potential_discount)
        applied_rebate = min(rebate_total, potential_rebate)

        # Any grants above and beyond the maximum ranks are refunded.
        applied_refund = refund_value * max(granted_ranks - grants_used, 0)

        return paid_cost - applied_discount - applied_rebate - applied_refund

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
                granted_ranks = self.bonus
                while available_ranks > 0:
                    cp_delta = (
                        self._cost_for(self.paid_ranks + available_ranks, granted_ranks)
                        - current_cost
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
            case "bp":
                # This is a placeholder for features where the breed
                # is not taken, and thus neither primary or secondary yet.
                return 0
            case "bp-primary":
                return self.character.bp_primary.value
            case "bp-secondary":
                return self.character.bp_secondary.value
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

    def get_costuming(self) -> models.CostumingData | None:
        return None

    def issues(self) -> list[Issue] | None:
        issues = super().issues() or []
        if (
            self.paid_ranks > 0
            and not self.can_buy_without_parent
            and (parent := self.parent)
            and not parent.value
        ):
            # The feature has been purchased, but not the parent.
            # While certain circumstances can grant a feature beneath a parent,
            # there should probably not be any where the feature is directly purchased
            # in that state.
            issues.append(
                Issue(
                    issue_code="parent-not-purchased",
                    reason=f"{self.display_name()} shouldn't be purchased without {parent.display_name()}",
                    feature_id=self.full_id,
                )
            )
        if self.value > 0 and (choices := self.choices):
            for choice in choices.values():
                if choice_issues := choice.issues():
                    issues.extend(choice_issues)
        return issues


class SkillController(FeatureController):
    definition: defs.SkillDef
    currency: str = "cp"


class PerkController(FeatureController):
    definition: defs.PerkDef
    currency: str = "cp"
