from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from abc import abstractproperty
from dataclasses import dataclass
from functools import cached_property
from functools import total_ordering
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Literal
from typing import Type

import pydantic
from packaging import version

from ..utils import dump_dict
from ..utils import maybe_iter
from . import base_models
from .decision import Decision


class CharacterController(ABC):
    model: base_models.CharacterModel
    engine: Engine
    mutated: bool = False
    _attribute_controllers: dict[str, AttributeController]

    # Copy of the model for use when the model is mutated by fails validation.
    _dumped_model: base_models.CharacterModel

    @property
    def ruleset(self):
        return self.engine.ruleset

    @abstractproperty
    def features(self) -> dict[str, BaseFeatureController]:
        ...

    def __init__(self, engine: Engine, model: base_models.CharacterModel):
        self.model = model
        self.engine = engine
        self._attribute_controllers = {}
        self._save_dump()

    def _save_dump(self) -> None:
        """Store the _dumped_model attribute."""
        self._dumped_model = self.dump_model()

    def _reload_dump(self) -> None:
        """Load the model from its serialized state.

        Typically used to repair the model after a mutation has failed validation.
        """
        self.model = self._dumped_model.copy(deep=True)
        self.clear_caches()

    def dump_dict(self) -> dict:
        """Returns a copy of the serialized model dictionary."""
        # exclude_unset is useful here because, for example, writing into a
        # dict on a model won't mark that field as set as far as the model is
        # concerned.
        data = dump_dict(self.model, exclude_unset=False, exclude_defaults=True)
        if not isinstance(data, dict):
            pass
        return data

    def dump_model(self) -> base_models.CharacterModel:
        """Returns a copy of the current model."""
        return self.model.copy(deep=True)

    def display_name(self, id: str) -> str:
        """Returns the display name of the given property."""
        if id in self.ruleset.display_names:
            return self.ruleset.display_names[id]
        if id in self.ruleset.features:
            return self.ruleset.features[id].name
        if id in self.ruleset.attribute_map:
            return self.ruleset.attribute_map[id].name
        return id.replace("_", " ").title()

    def plural_name(self, id: str) -> str:
        """Returns the plural name of the given property."""
        display_name = self.display_name(id)
        return self.ruleset.pluralize(display_name)

    def display_priority(self, feature_type: str) -> int:
        """Returns the display priority of the given feature type.

        By default, all feature types have the same priority. Subclasses can
        override this to change the order in which feature types are displayed.

        Lower valued priorities are displayed first.
        """
        return 1

    def list_features(
        self,
        type: str | None = None,
        taken: bool = True,
        available: bool = True,
    ) -> Iterable[BaseFeatureController]:
        """List all features of the given type."""
        if taken:
            for id, fc in self.features.items():
                if type and fc.definition.type != type:
                    continue
                if fc.value <= 0:
                    continue
                if available and not fc.can_increase():
                    continue
                if fc.option_def and not fc.option:
                    # This is feature controller belongs to an option feature
                    # that doesn't have an option selected. It represents the
                    # "raw" skill and should appear in the "untaken" list even
                    # though it has a value associated.
                    continue
                yield fc
        else:
            for id, definition in self.ruleset.features.items():
                if id in self.features and self.get(id) > 0:
                    continue
                if type and definition.type != type:
                    continue
                fc = self.feature_controller(id)
                rd = fc.can_increase()
                if available and not (rd or rd.needs_option):
                    continue
                yield fc

    @abstractmethod
    def clear_caches(self):
        """Clear any cached data that might need to be recomputed upon mutating the character model."""

    def reconcile(self):
        """Perform any necessary reconciliation of the character model."""
        for feat in list(self.features.values()):
            feat.reconcile()

    def apply(
        self, mutation: base_models.Mutation | str, raise_exc: bool = True
    ) -> Decision:
        rd: Decision
        if isinstance(mutation, str):
            mutation = base_models.RankMutation.parse(mutation)
        try:
            match mutation:
                case base_models.RankMutation():
                    rd = self.purchase(mutation)
                case base_models.ChoiceMutation():
                    rd = self.choose(mutation)
                case _:
                    rd = Decision(
                        success=False, reason=f"Mutation {mutation} unsupported."
                    )
        except Exception as exc:
            if raise_exc:
                # Most of the time, we want to raise exceptions. A production environment
                # might prefer to get all decisions back in Decision form, so the exception
                # can alternatively be converted.
                self._reload_dump()
                raise
            rd = Decision(
                success=False,
                reason=f"The rules engine raised a {type(exc)} exception.",
                exception=str(exc),
            )
        if rd:
            validated = self.validate()
            if not validated:
                rd = validated
        if not rd:
            self._reload_dump()
        else:
            self._save_dump()
            self.mutated = True
        return rd

    def validate(self) -> Decision:
        """Validate the current model state.

        In some cases, applying a mutation may affect validity in ways that are difficult to
        predict (or prevent). Validate will be called following mutations, so feature requirements
        and other state should be checked. If the valdity check fails, the mutation will be reverted.
        """
        return Decision.OK

    def has_prop(self, expr: str | base_models.PropExpression) -> bool:
        """Check whether the character has _any_ property (feature, attribute, etc) with the given name."""
        expr = base_models.PropExpression.parse(expr)
        return expr.prop in self.engine.attribute_map or expr.full_id in self.features

    def controller(
        self, expr: base_models.PropExpression | str
    ) -> PropertyController | None:
        expr = base_models.PropExpression.parse(expr)
        controller: PropertyController | None = None
        prefix, expr = expr.pop()
        if prefix:
            # Follow the prefix path to the appropriate controller.
            controller = self.controller(prefix)
            while prefix:
                prefix, expr = expr.pop()
                if prefix:
                    controller = controller.subcontroller(prefix)
            return controller.subcontroller(expr.full_id)

        if expr.prop in self.ruleset.features:
            # Feature controllers are retrieved by prop and option. Do not
            # include attribute or slot in the request.
            return self.feature_controller(expr)
        elif attr := self.ruleset.attribute_map.get(expr.prop):
            if attr.scoped:
                raise ValueError(
                    f"Attribute {expr.prop} is scoped and can not be requested without a containing property."
                )
            return self.attribute_controller(expr)
        return None

    @abstractmethod
    def feature_controller(
        self, expr: str | base_models.PropExpression
    ) -> BaseFeatureController:
        """Returns a feature controller for the given feature id."""

    def attribute_controller(
        self, expr: str | base_models.PropExpression
    ) -> AttributeController:
        """Returns an attribute controller for the given attribute id."""
        expr = base_models.PropExpression.parse(expr)
        controller: AttributeController | None = None

        if controller := self._attribute_controllers.get(expr.prop):
            return controller

        attr: base_models.Attribute
        if attr := self.engine.attribute_map.get(expr.prop):
            # There are a few different ways an attribute might be stored or computed.
            if attr.scoped:
                # Scoped attributes are never stored on the character controller.
                pass
            elif hasattr(self, attr.property_name or attr.id):
                attr_value: PropertyController | Callable | int = getattr(
                    self, attr.property_name or attr.id
                )
                if isinstance(attr_value, PropertyController):
                    controller = attr_value
                else:
                    controller = SimpleAttributeWrapper(expr.full_id, self)
        if controller:
            self._attribute_controllers[expr.prop] = controller
            return controller
        raise ValueError(f"Attribute {expr.full_id} not found.")

    def get(self, expr: str | base_models.PropExpression) -> int:
        """Retrieve the value of an arbitrary property (feature, attribute, etc).

        The base implementation only knows how to retrieve attributes. If the attribute
        is configured with `compute`, the named property is retrieved. Otherwise, checks
        the character controller for a property named either `property_name` or whatever
        the attribute's ID is and returns that. If none of the above work, just returns
        the attribute's configured `default_value`.

        Implementations can use this base implementation for attribute retrieval, but must
        add support for features.
        """
        expr = base_models.PropExpression.parse(expr)
        if controller := self.controller(expr):
            return controller.get(expr.noprefix())
        return 0

    @cached_property
    def flags(self) -> dict[str, base_models.FlagValues]:
        flags = self.ruleset.default_flags.copy()
        for f, value in self.model.metadata.flags.items():
            if value is None:
                continue
            if f not in flags:
                flags[f] = value
            elif isinstance(value, list) or isinstance(flags[f], list):
                # Coerce both to lists and combine
                flags[f] = list(maybe_iter(flags[f])) + list(maybe_iter(value))
            else:
                # Both are scalar. Overwrite.
                flags[f] = value
        return flags

    def get_options(self, expr: str) -> dict[str, int]:
        """Retrieves the options (and their values) for a particular property or feature."""
        return {}

    @abstractmethod
    def can_purchase(self, entry: base_models.RankMutation) -> Decision:
        ...

    @abstractmethod
    def purchase(self, entry: base_models.RankMutation) -> Decision:
        ...

    @abstractmethod
    def choose(self, entry: base_models.ChoiceMutation) -> Decision:
        ...

    def meets_requirements(self, requirements: base_models.Requirements) -> Decision:
        messages: list[str] = []
        for req in maybe_iter(requirements):
            if isinstance(req, str):
                # It's unlikely that an unparsed string gets here, but if so,
                # go ahead and parse it.
                req = base_models.PropExpression.parse(req)
            if not (rd := req.evaluate(self)):
                messages.append(rd.reason)
        if messages:
            messages = ["Not all requirements are met."] + messages
        return Decision(
            success=not (messages), reason="\n".join(messages) if messages else None
        )

    def options_values_for_feature(
        self, feature_id: str, exclude_taken: bool = False
    ) -> set[str]:
        """Retrieve the options valid for a feature for this character.

        Args:
            feature_id: Identifier of the feature to check.
            exclude_taken: If this character has already taken
                this feature, removes any that have already been taken.
        """
        feature_def = self.engine.feature_defs[feature_id]
        option_def = feature_def.option
        if not (option_def.values or option_def.inherit):
            return set()
        options_excluded: set[str] = set()
        if exclude_taken and (taken_options := self.get_options(feature_id)):
            if not option_def.multiple:
                # The feature can only have a single option and it already
                # has one, so no other options are legal.
                return set()
            elif not isinstance(
                option_def.multiple, bool
            ) and option_def.multiple <= len(taken_options):
                # The feature can have multiple options, but already has the limit (or more).
                return set()
            options_excluded = set(taken_options.keys())

        # If needed, option requirements can be specified in terms of flags.
        # This dict keeps track of which options come from which flags.
        option_source: dict[str, str] = {}

        if option_def.inherit:
            expr = base_models.PropExpression.parse(option_def.inherit)
            legal_values = set(self.get_options(expr.prop))
            # If expr has a value specified, the only legal options are the
            # ones that meet this requirement.
            if expr.value:
                for option in legal_values.copy():
                    req = expr.copy(update={"option": option})
                    if not req.evaluate(self):
                        legal_values.remove(option)
        else:
            legal_values = set(option_def.values)
            for option in legal_values.copy():
                if option.startswith("$"):
                    legal_values.remove(option)
                    flag = option[1:]
                    extra_values = self.flags.get(flag, [])
                    str_values: list[str] = [str(ev) for ev in maybe_iter(extra_values)]
                    additions = {ev for ev in str_values if not ev.startswith("-")}
                    removals = {ev for ev in str_values if ev.startswith("-")}
                    for value in additions:
                        option_source[value] = option
                    legal_values ^= removals
                    legal_values |= additions

        legal_values -= options_excluded

        # An option definition can specify requirements for each option. If a
        # requirement is specified and not met, remove it from the set.
        if option_def.requires:
            unmet = set()
            for option in legal_values:
                # Check if the option is specified explicitly in the requirements
                if option in option_def.requires:
                    req = option_def.requires[option]
                    if not self.meets_requirements(req):
                        unmet.add(option)
                # Check if the option is specified generally by its flag name
                elif (
                    source := option_source.get(option)
                ) and source in option_def.requires:
                    req = option_def.requires[source]
                    if not self.meets_requirements(req):
                        unmet.add(option)
            legal_values ^= unmet

        return legal_values

    def option_satisfies_definition(
        self,
        feature_id: str,
        option_value: str,
        exclude_taken: bool = False,
    ) -> bool:
        feature_def = self.engine.feature_defs[feature_id]
        option_def = feature_def.option
        if not option_def and not option_value:
            # No option needed, no option provided. Good.
            return True
        if not option_def and option_value:
            # There's no option definition, if an option was provided
            # then it's wrong.
            return False
        if option_def.freeform:
            # The values are just suggestions. We may want to
            # filter for profanity or something, but otherwise
            # anything goes.
            return True
        # Otherwise, the option must be in a specific set of values.
        return option_value in self.options_values_for_feature(
            feature_id, exclude_taken=exclude_taken
        )

    def describe_mutation(self, mutation: base_models.Mutation) -> str:
        """Returns a human-readable description of the given mutation."""
        match mutation:
            case base_models.RankMutation():
                if mutation.option:
                    name = f"{self.display_name(mutation.id)} [{mutation.option}] x{abs(mutation.ranks)}"
                else:
                    name = f"{self.display_name(mutation.id)} x{abs(mutation.ranks)}"
                if mutation.ranks > 0:
                    return f"Purchase {name}"
                elif mutation.ranks == 0:
                    # WTF?
                    return f"Unrecognized rank mutation on {name}"
                else:
                    return f"Remove {name}"
            case base_models.ChoiceMutation():
                feature = self.feature_controller(mutation.id)
                choice = feature.choices.get(mutation.choice)
                choice_name = getattr(choice, "name", mutation.choice.title())
                selection = self.display_name(mutation.value)
                if mutation.remove:
                    return f"Unchose '{selection}' for choice {choice_name} of {feature.display_name()}"
                return f"Chose '{selection}' for choice {choice_name} of {feature.display_name()}"
            case _:
                return repr(mutation)


@total_ordering
class PropertyController(ABC):
    id: str
    full_id: str
    expression: base_models.PropExpression
    character: CharacterController
    description: str | None
    _propagation_data: dict[str, PropagationData]
    _subcontrollers: dict[str, PropertyController]

    def __init__(self, full_id: str, character: CharacterController):
        self._propagation_data = {}
        self._subcontrollers = {}
        self.expression = base_models.PropExpression.parse(full_id)
        self.full_id = full_id
        self.id = self.expression.prop
        self.character = character

    def display_name(self) -> str:
        name = self.character.display_name(self.expression.prop)
        if self.option:
            name += f" [{self.option}]"
        return name

    @property
    def value(self) -> int:
        """Returns the computed value for this property.

        Subclasses should override this. The default implementation returns only the applied bonuses.
        """
        return self.bonus

    @property
    def bonus(self) -> int:
        """Returns the bonus values applied to this property by other controllers."""
        return sum(p.grants for p in self._propagation_data.values())

    @property
    def option(self) -> str | None:
        return self.expression.option

    @property
    def max_value(self) -> int:
        return self.value

    def get(self, expr: str | base_models.PropExpression) -> int:
        expr = base_models.PropExpression.parse(expr)
        prefix, expr = expr.pop()
        controller = self
        while prefix:
            controller = controller.subcontroller(prefix)
            prefix, expr = expr.pop()

        if controller is self:
            if expr.single is not None:
                return self.max_value
            return self.value
        return controller.get(expr)

    def reconcile(self) -> None:
        """Override to update computations on change."""

    def propagate(self, data: PropagationData) -> None:
        """Used to accept things like granted ranks from other sources."""
        if not data and data.source not in self._propagation_data:
            return
        if data:
            self._propagation_data[data.source] = data
        else:
            del self._propagation_data[data.source]
        self.reconcile()

    def subcontroller(
        self, expr: str | base_models.PropExpression
    ) -> PropertyController | None:
        """Returns a subcontroller for the given expression, if possible.

        The default implementation supports attribute controllers. If a "simple" attribute
        (one that does not return its own controller) is requested, it will be wrapped in a
        SimpleAttributeWrapper.
        """
        expr = base_models.PropExpression.parse(expr)
        if expr.prefixes:
            raise ValueError(
                f"Prefix path parsing is not available in `subcontroller` (expr={expr})."
            )
        controller: PropertyController | None = None
        if controller := self._subcontrollers.get(expr.full_id):
            return controller
        if attr := self.character.engine.attribute_map.get(expr.prop):
            # There are a few different ways an attribute might be stored or computed.
            if not attr.scoped:
                # Global attributes are never stored on property controllers.
                return None
            if hasattr(self, attr.property_name or attr.id):
                # If the attribute is stored on this controller, we can just return it.
                # If it's a 'simple' attribute (it just returns an integer)
                attr_value: PropertyController | int = getattr(
                    self, attr.property_name or attr.id
                )
                if isinstance(attr_value, PropertyController):
                    controller = attr_value
                else:
                    controller = SimpleAttributeWrapper(expr, self.character, self)
        self._subcontrollers[expr.full_id] = controller
        return controller

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        match other:
            case PropertyController():
                return self.value == other.value
            case _:
                return self.value == other

    def __lt__(self, other: Any) -> bool:
        match other:
            case PropertyController():
                return self.value < other.value
            case _:
                return self.value < other


class BaseFeatureController(PropertyController):
    rank_name_labels: tuple[str, str] = ("rank", "ranks")

    @cached_property
    def expr(self) -> base_models.PropExpression:
        return base_models.PropExpression.parse(self.id)

    @cached_property
    def definition(self) -> base_models.BaseFeatureDef:
        return self.character.engine.feature_defs[self.expr.prop]

    @property
    def parent(self) -> BaseFeatureController | None:
        if self.definition.parent is None:
            return None
        return self.character.feature_controller(self.definition.parent)

    @property
    def tags(self) -> set[str]:
        return self.definition.tags

    @property
    def parent_def(self) -> base_models.BaseFeatureDef | None:
        return self.definition.parent_def

    @property
    def children(self) -> list[BaseFeatureController]:
        children = [
            self.character.feature_controller(expr)
            for expr in self.definition.child_ids
        ]
        children.sort(key=lambda f: f.full_id)
        return children

    @property
    def taken_children(self) -> list[BaseFeatureController]:
        return [c for c in self.children if c.value > 0]

    @property
    def next_value(self) -> int | None:
        """What's the next value that can be purchased?

        Normally, the next value available for purchase is the current value + 1.

        In some cases, such as when in Geas when selecting your first class level,
        the class jumps from 0 directly to 2, and 1 is not a possible value.
        """
        if self.max_ranks == "unlimited" or self.value < self.max_ranks:
            return self.value + 1

    @property
    def min_value(self) -> int | None:
        """What's the lowest value that we can reduce to?

        Normally this will be 0, but in some cases such as when a feature
        has been granted ranks or you're asking about a Geas starting class's
        level, it may not be possible to reduce it all the way.
        """
        return self.granted_ranks

    @property
    def description(self) -> str | None:
        return self.definition.description

    @property
    def short_description(self) -> str | None:
        if self.definition.short_description:
            return self.definition.short_description
        if self.description:
            descr = self.description.split("\n")[0]
            if len(descr) > 100:
                return descr[:100] + "…"
            return descr
        return None

    @property
    def max_ranks(self) -> int:
        if self.definition.ranks == "unlimited":
            # Arbitrarily chosen large int.
            return 101
        return self.definition.ranks

    @property
    def type_name(self) -> str:
        return self.character.display_name(self.feature_type)

    @property
    def option_def(self) -> base_models.OptionDef | None:
        return self.definition.option

    @property
    def purchase_cost_string(self) -> str | None:
        return None

    @property
    def category(self) -> str | None:
        return self.definition.category

    @property
    def is_concrete(self) -> bool:
        return (
            (self.option_def and self.option) or not self.option_def
        ) and self.value > 0

    @property
    def is_taken(self) -> bool:
        if self.option_def and not self.option:
            # The "core" controller for an option feature is never
            # considered taken. Only its subfeatures can be "taken", even though
            # the controller reports a value for it for purposes of the requirement parser.
            return False
        return self.value > 0

    @cached_property
    def feature_type(self) -> str:
        return self.definition.type

    @property
    def is_option_template(self) -> str:
        """True if this is an option template feature.

        For example, "Lore" is an option template feature, while
        "Lore [History]" is an option feature.
        The template should never appear on a character sheet except
        in the "Add New {Type}" section of each type group. However,
        the controller still needs to exist, as it is used to determine
        whether a new option feature can be added based on it, and also
        to provide a property for other features to use as a prerequisite.
        (e.g. "Requires three ranks of Lore").
        """
        return self.option_def and not self.option

    @property
    def can_take_new_option(self) -> bool:
        """True if this option template can take a new option.

        False if no more options may be taken, or if this is not an option template.
        """
        if not self.option_def:
            return False
        taken = len(self.taken_options)
        if isinstance(self.option_def.multiple, bool):
            if not self.option_def.multiple and taken:
                return False
            return True
        if (
            isinstance(self.option_def.multiple, int)
            and taken >= self.option_def.multiple
        ):
            return False
        if self.option_def.inherit:
            return True
        return True

    @property
    def taken_options(self) -> dict[str, int]:
        return {}

    @property
    def available_options(self) -> list[str] | None:
        if not self.option_def:
            return None
        return sorted(
            self.character.options_values_for_feature(self.id, exclude_taken=True)
        )

    @property
    def available_ranks(self) -> int:
        """How many ranks are available to be taken?

        This isn't just the number of ranks left, but the number of ranks that
        the character could buy right now. For example, if the character has
        3 ranks in a feature that has a max of 5, then they have 2 ranks available,
        but only if they have enough CP to buy them and they meet any other requirements.
        """
        theoretical_max = self.possible_ranks
        if theoretical_max <= 0:
            return 0
        if rd := self.can_increase(theoretical_max):
            return theoretical_max
        return rd.amount or 0

    @property
    def possible_ranks(self) -> int:
        """The number of ranks left to be taken, regardless of whether they can be taken right now."""
        return self.max_ranks - self.value

    @property
    def purchased_ranks(self) -> int:
        return self.value

    @property
    def granted_ranks(self) -> int:
        return 0

    def rank_name(self, value: int | None = None):
        if value is None:
            value = self.value
        if value == 1:
            return self.rank_name_labels[0]
        else:
            return self.rank_name_labels[1]

    @property
    def explain(self) -> list[str]:
        """Returns a list of strings explaining how the ranks were obtained."""
        if self.value <= 0:
            return []
        if self.definition.ranks == 1 and self.purchased_ranks == 1:
            return ["You have taken this feature."]
        reasons = []
        if self.purchased_ranks > 0:
            reasons.append(
                f"You have taken {self.purchased_ranks} {self.rank_name(self.purchased_ranks)}."
            )
        if self.granted_ranks > 0:
            reasons.append(
                f"You have been granted {self.granted_ranks} {self.rank_name(self.granted_ranks)}."
            )
        return reasons

    def can_increase(self, value: int = 1) -> Decision:
        return Decision(success=False, reason=f"Increase unsupported for {type(self)}")

    def can_decrease(self, value: int = 1) -> Decision:
        return Decision(success=False, reason=f"Decrease unsupported for {type(self)}")

    def increase(self, value: int) -> Decision:
        return Decision(success=False, reason=f"Increase unsupported for {type(self)}")

    def decrease(self, value: int) -> Decision:
        return Decision(success=False, reason=f"Decrease unsupported for {type(self)}")

    @property
    def currency(self) -> str | None:
        return None

    @property
    def feature_list_name(self) -> str:
        if self.option_def and not self.option:
            # This is feature controller belongs to an option feature
            # that doesn't have an option selected. It represents the
            # "raw" skill, and it doesn't have anything to display.
            return self.display_name()
        if self.definition.has_ranks and self.value > 0:
            return f"{self.display_name()} x{self.value}"
        return self.display_name()

    def __str__(self) -> str:
        return self.feature_list_name


class AttributeController(PropertyController):
    @cached_property
    def definition(self) -> base_models.Attribute:
        return self.character.engine.attribute_map[self.id]

    def __str__(self) -> str:
        return f"{self.definition.name}: {self.value}"


class ChoiceController(ABC):
    @abstractproperty
    def id(self) -> str:
        ...

    @abstractproperty
    def name(self) -> str:
        ...

    @property
    def description(self) -> str | None:
        return None

    @property
    def advertise(self) -> bool:
        """If True, the top-level character sheet will note when this choice is available."""
        return True

    @property
    def limit(self) -> int | Literal["unlimited"]:
        return 1

    @property
    def multi(self) -> bool:
        return False

    @property
    def choices_remaining(self) -> int:
        if self.limit == "unlimited":
            return 999
        return self.limit - len(self.taken_choices())

    @abstractmethod
    def available_choices(self) -> dict[str, str]:
        """Dictionary of available choices and their readable descriptions."""

    @abstractmethod
    def taken_choices(self) -> dict[str, str]:
        """Dict of choice IDs that have been taken and a printable name."""

    def removeable_choices(self) -> set[str]:
        """Set of choice IDs that are removable.

        If not implemented, all choices are assumed removable.
        """
        return set(self.taken_choices().keys())

    @abstractmethod
    def choose(self, choice: str) -> Decision:
        """Choose the given choice."""

    @abstractmethod
    def unchoose(self, choice: str) -> Decision:
        """Unchoose the given choice."""


class SimpleAttributeWrapper(AttributeController):
    def __init__(
        self,
        full_id: str,
        character: CharacterController,
        subcontroller: PropertyController | None = None,
    ):
        super().__init__(full_id, character)
        self._subcontroller = subcontroller
        if self.definition.scoped and not subcontroller:
            raise ValueError(f"Scoped attribute {self.id} requires a subcontroller.")
        if not self.definition.scoped and subcontroller:
            raise ValueError(
                f"Attribute {self.id} is not scoped and cannot have a subcontroller."
            )

    @property
    def value(self) -> int:
        base_value = super().value
        controller = self._subcontroller or self.character
        attr = self.definition
        if attr_value := getattr(controller, attr.property_name or attr.id, None):
            if isinstance(attr_value, PropertyController):
                raise RuntimeError(
                    f"SimpleAttributeWrapper should only wrap simple attributes; {attr.id} has property controller {attr_value}"
                )
            elif isinstance(attr_value, Callable):
                try:
                    return base_value + attr_value(self.expression)
                except TypeError:
                    return base_value + attr_value()
            return base_value + attr_value
        return attr.default_value + base_value


class Engine(ABC):
    def __init__(self, ruleset: base_models.BaseRuleset):
        self._ruleset = ruleset

    @property
    def ruleset(self) -> base_models.BaseRuleset:
        return self._ruleset

    @cached_property
    def attribute_map(self) -> dict[str, base_models.Attribute]:
        return self.ruleset.attribute_map

    @cached_property
    def feature_defs(self) -> dict[str, base_models.BaseFeatureDef]:
        """Convenience property that provides all feature definitions."""
        return self.ruleset.features

    @abstractproperty
    def sheet_type(self) -> Type[base_models.CharacterModel]:
        ...

    @abstractproperty
    def character_controller(self) -> Type[CharacterController]:
        return CharacterController

    def new_character(self, **data) -> CharacterController:
        return self.character_controller(
            self,
            self.sheet_type(
                ruleset_id=self.ruleset.id, ruleset_version=self.ruleset.version, **data
            ),
        )

    def load_character(self, data: dict) -> CharacterController:
        """Load the given character data with this ruleset.

        Returns:
            A character sheet of appropriate subclass.

        Raises:
            ValueError: if the character is not compatible with this ruleset.
                By default, characters are only comaptible with the ruleset they
                were originally written with.
        """
        updated_data = self.update_data(data)
        model = pydantic.parse_obj_as(self.sheet_type, updated_data)
        c = self.character_controller(self, model)
        c.reconcile()
        return c

    def update_data(self, data: dict) -> dict:
        """If the data is from a different but compatible rules version, update it.

        The default behavior is to reject any character data made with a different ruleset ID,
        and assume newer versions are backward (but not forward).

        Raises:
            ValueError: if the character is not compatible with this ruleset.
                By default, characters are only comaptible with the ruleset they
                were originally written with.
        """
        if data["ruleset_id"] != self.ruleset.id:
            raise ValueError(
                f'Can not load character id={data["id"]}, ruleset={data["ruleset_id"]} with ruleset {self.ruleset.id}'
            )
        if version.parse(self.ruleset.version) < version.parse(data["ruleset_version"]):
            raise ValueError(
                f'Can not load character id={data["id"]}, ruleset={data["ruleset_id"]} v{data["ruleset_version"]}'
                f" with ruleset {self.ruleset.id} v{self.ruleset.version}"
            )
        return data


@dataclass
class PropagationData:
    source: str
    target: base_models.PropExpression
    grants: int = 0
    discount: list[base_models.Discount] | None = None

    def __bool__(self) -> bool:
        return bool(self.grants) or bool(self.discount)
