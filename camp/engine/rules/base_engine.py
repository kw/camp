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
    def features(self) -> dict[str, BaseFeatureController]: ...

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
        self.model = self._dumped_model.model_copy(deep=True)
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
        return self.model.model_copy(deep=True)

    def tag_name(self, tag: str) -> str | None:
        return tag.replace("_", " ").title()

    def display_name(self, id: str, use_abbrev: bool = False) -> str:
        """Returns the display name of the given property."""
        if use_abbrev and (abbrev := self.ruleset.abbreviated_name(id)):
            return abbrev
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
        filter_subfeatures: bool = True,
    ) -> Iterable[BaseFeatureController]:
        """List all features of the given type."""
        if taken:
            for id, fc in list(self.features.items()):
                if fc.value <= 0 and fc.unused_bonus <= 0:
                    # It's not actually taken...
                    continue
                if type and fc.definition.type != type:
                    continue
                if available and not fc.can_increase():
                    continue
                if fc.is_superseded and not fc.has_available_choices:
                    continue
                if fc.should_show_in_list or not filter_subfeatures:
                    yield fc
        else:
            for id, definition in self.ruleset.features.items():
                if id in self.features and (fc := self.feature_controller(id)):
                    if fc.should_show_in_list:
                        continue
                if type and definition.type != type:
                    continue
                fc = self.feature_controller(id)
                rd = fc.can_increase()
                if available:
                    if not rd and fc.is_option_template:
                        # Even if the option template isn't available, some options might still be available.
                        # Consider a character with 1 CP trying to purchase Lore: Noble. Lore costs 2 CP, so it won't
                        # be displayed. However, the character is an Edosite and has a -1 discount on Lore: Noble, and
                        # viewing its page directly allows it to be purchased.
                        for ofc in fc.option_controllers(taken=False).values():
                            if ofc.can_increase():
                                yield ofc
                        continue
                    elif not (rd or rd.needs_option):
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
        self,
        mutation: base_models.Mutation | str,
        raise_exc: bool = True,
        dry_run: bool = False,
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
        if dry_run or not rd:
            self._reload_dump()
            self.clear_caches()
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
        # Basic validity: Do all features claim to be valid?
        features = list(self.features.values())
        for feature in features:
            feature.reconcile()
        for feature in features:
            if not (rd := feature.validate()):
                return rd
        return Decision.OK

    def issues(self) -> list[base_models.Issue]:
        issues: list[base_models.Issue] = []
        for feature in list(self.features.values()):
            if new_issues := feature.issues():
                issues.extend(new_issues)
        return issues

    def fully_valid(self) -> Decision:
        if not (rd := self.validate()):
            return rd
        if issues := self.issues():
            if len(issues) == 1:
                return Decision(success=False, reason=issues[0].reason)
            return Decision(
                success=False,
                reason=f"{len(issues)} issues detected, including: {issues[0].reason}",
            )
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
            while prefix and controller:
                prefix, expr = expr.pop()
                if prefix:
                    controller = controller.subcontroller(prefix)
            if controller:
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

        if controller := self._attribute_controllers.get(expr.full_id):
            return controller

        attr = self.engine.attribute_map.get(expr.prop)
        if attr is not None:
            # There are a few different ways an attribute might be stored or computed.
            if attr.scoped:
                # Scoped attributes are never stored on the character controller.
                pass
            else:
                attr_value = getattr(self, attr.property_id, None)
                if attr_value is not None:
                    if isinstance(attr_value, AttributeController):
                        controller = attr_value
                    else:
                        controller = SimpleAttributeWrapper(expr.full_id, self)
        if controller:
            self._attribute_controllers[expr.full_id] = controller
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
    def can_purchase(self, entry: base_models.RankMutation) -> Decision: ...

    @abstractmethod
    def purchase(self, entry: base_models.RankMutation) -> Decision: ...

    @abstractmethod
    def choose(self, entry: base_models.ChoiceMutation) -> Decision: ...

    def meets_requirements(
        self, requirement: base_models.Requirement | str, prop_id: str | None = None
    ) -> Decision:
        messages: list[str] = []
        if isinstance(requirement, str):
            # It's unlikely that an unparsed string gets here, but if so,
            # go ahead and parse it.
            requirement = base_models.parse_req(requirement)
        if not (rd := requirement.evaluate(self)):
            messages.append(rd.reason)
        if messages:
            if prop_id:
                header = (
                    f"Not all requirements are met for {self.display_name(prop_id)}."
                )
            else:
                header = "Not all requirements are met."
            messages = [header] + messages
        return Decision(
            success=not (messages),
            reason="\n".join(messages) if messages else "Unknown",
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
        if option_def is None:
            return set()
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
            legal_values = set(option_def.values) if option_def.values else set()
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
        if option_def is None:
            # None option_def is only compatible with empty option value.
            return not option_value
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
                if feature.choices is None:
                    return "Choice selection on feature with no choices."
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
        while prefix and controller:
            controller = controller.subcontroller(prefix)
            prefix, expr = expr.pop()

        if controller is self:
            if expr.single is not None:
                return self.max_value
            return self.value
        if controller is None:
            return 0
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
            if (attr_value := getattr(self, attr.property_id, None)) is not None:
                # If the attribute is stored on this controller, we can just return it.
                # If it's a 'simple' attribute (it just returns an integer)
                if isinstance(attr_value, PropertyController):
                    controller = attr_value
                else:
                    controller = SimpleAttributeWrapper(
                        expr.full_id, self.character, self
                    )
        if controller is not None:
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
        return base_models.PropExpression.parse(self.full_id)

    @cached_property
    def definition(self) -> base_models.BaseFeatureDef:
        return self.character.engine.feature_defs[self.expr.prop]

    @cached_property
    def extra_parent_ids(self) -> frozenset[str]:
        if parent_id := self.definition.parent:
            if uncles := self.character.ruleset.features[parent_id]._uncles:
                return frozenset(uncles)
        return frozenset()

    @property
    def parent(self) -> BaseFeatureController | None:
        if self.definition.parent is None:
            return None
        parent = self.character.feature_controller(self.definition.parent)
        if parent.value == 0 and (extra_ids := self.extra_parent_ids):
            for eid in extra_ids:
                extra_controller = self.character.feature_controller(eid)
                if extra_controller.value > 0:
                    return extra_controller
        return parent

    @property
    def supersedes(self) -> BaseFeatureController | None:
        if self.definition.supersedes is None:
            return None
        return self.character.feature_controller(self.definition.supersedes)

    @property
    def superseded_by(self) -> BaseFeatureController | None:
        if self.definition.superseded_by is None:
            return None
        return self.character.feature_controller(self.definition.superseded_by)

    @property
    def is_superseded(self) -> bool:
        if superseded_by := self.superseded_by:
            return superseded_by.value > 0
        return False

    @cached_property
    def tags(self) -> set[str]:
        return self.definition.tags

    @property
    def parent_def(self) -> base_models.BaseFeatureDef | None:
        return self.definition.parent_def

    @cached_property
    def child_ids(self) -> frozenset[str]:
        children = self.definition.child_ids.copy()
        if self.definition.inherit_children:
            for inherit_id in self.definition.inherit_children:
                feature = self.character.feature_controller(inherit_id)
                new_children = feature.child_ids
                children.update(new_children)
        return frozenset(children)

    @property
    def children(self) -> list[BaseFeatureController]:
        children: list[BaseFeatureController] = []
        for expr in self.child_ids:
            fc = self.character.feature_controller(expr)
            children.append(fc)
            if fc.is_option_template:
                children.extend(fc.option_controllers().values())

        children.sort(key=lambda f: f.display_name())
        children.sort(key=lambda f: self.character.display_priority(f.feature_type))
        return children

    @property
    def taken_children(self) -> list[BaseFeatureController]:
        return [c for c in self.children if c.value > 0 and not c.is_option_template]

    @property
    def meets_requirements(self) -> Decision:
        return self.character.meets_requirements(self.definition.requires, self.full_id)

    @abstractproperty
    def has_available_choices(self) -> bool: ...

    @abstractproperty
    def choices(self) -> dict[str, ChoiceController] | None: ...

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
        return self.bonus

    @property
    def description(self) -> str | None:
        if self.option and (descr := self.option_description(self.option)):
            return f"""{self.definition.description}\n\n## {self.option}\n\n{descr}"""
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

    def option_description(self, option: str) -> str | None:
        if option_def := self.option_def:
            if descriptions := option_def.descriptions:
                return descriptions.get(option)
        return None

    def describe_option(self, option: str) -> str:
        if descr := self.option_description(option):
            return f"{option}: {descr}"
        return option

    @property
    def unlimited_ranks(self) -> bool:
        return self.definition.ranks == "unlimited"

    @property
    def max_ranks(self) -> int:
        if self.unlimited_ranks:
            # Arbitrarily chosen large int.
            return 101
        return self.definition.ranks  # type: ignore

    @property
    def type_name(self) -> str:
        return self.character.display_name(self.feature_type)

    @property
    def option(self) -> str | None:
        if option_def := self.definition.option:
            if option_def.inherit:
                # The inherit field names a real option skill. We should report the
                # name of that option.
                template = self.character.feature_controller(option_def.inherit)
                options = template.taken_options.keys()
                if len(options) == 1:
                    return list(options)[0]
                return "???"
            return self.expr.option
        return None

    @property
    def option_def(self) -> base_models.OptionDef | None:
        if (option_def := self.definition.option) and not option_def.inherit:
            return option_def
        return None

    def option_controllers(
        self, taken: bool = True
    ) -> dict[str, BaseFeatureController]:
        if not self.option_def:
            return {}
        controllers = {
            c.option: c
            for c in self.character.features.values()
            if c.id == self.id and c.option and c.value > 0
        }
        if not taken and (options := self.available_options):
            for option in options:
                if option not in controllers:
                    controllers[option] = self.with_option(option)
        return controllers

    def with_option(self, option: str) -> BaseFeatureController:
        option_expr = self.expression.model_copy(update={"option": option})
        return self.character.feature_controller(option_expr)

    @property
    def purchase_cost_string(self) -> str | None:
        return None

    @property
    def category(self) -> str | None:
        return self.definition.category

    @property
    def category_priority(self) -> float:
        return self.definition.category_priority

    @property
    def category_tags(self) -> set[str]:
        return set()

    @property
    def is_concrete(self) -> bool:
        return (
            bool((self.option_def and self.option) or not self.option_def)
            and self.value > 0
        )

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
    def is_option_template(self) -> bool:
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
        return bool(self.option_def and not self.option)

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
        return True

    @property
    def badges(self) -> list[tuple[str, str]]:
        badges = []
        if issues := self.issues():
            if len(issues) == 1:
                badges.append(("warning", "1 issue"))
            else:
                badges.append(("warning", f"{len(issues)} issues"))
        return badges

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
    def should_show_in_list(self) -> bool:
        """Whether the feature should be shown in the list of "taken" features.

        Subclasses may want to override this to show features that have no current
        value but need to be displayed for some other reason.
        """
        return self.value > 0 and not self.is_option_template

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

    @abstractproperty
    def purchased_ranks(self) -> int:
        """How many ranks the player has intentionally purchased, whether or not they're used."""
        return 0

    @property
    def unused_bonus(self) -> int:
        return 0

    @property
    def paid_ranks(self) -> int:
        """Number of ranks purchased that actually need to be paid for with some currency.

        This is generally equal to `purchased_ranks`, but when grants push the total over the
        feature's maximum, these start to be refunded. They remain on the sheet in case the
        grants are revoked in the future due to an undo, a sellback, a class level swap, etc.
        """
        total = self.purchased_ranks + self.bonus
        max_ranks = self.max_ranks
        if total <= max_ranks:
            return self.purchased_ranks
        # The feature is at maximum. Only pay for ranks that haven't been granted.
        # Note that the total grants could also exceed max_ranks. This is more likely
        # to happen with single-rank features like weapon proficiencies that a character
        # might receive from multiple classes.
        if self.bonus < max_ranks:
            return max_ranks - self.bonus
        return 0

    def sort_key(self) -> Any:
        return self.display_name()

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
        if self.bonus > 0:
            reasons.append(
                f"You have been granted {self.bonus} {self.rank_name(self.bonus)}."
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

    @abstractproperty
    def feature_list_name(self) -> str: ...

    def validate(self) -> Decision:
        """Check that the feature is valid.

        What does validity really mean? For the purposes of this app, let's consider _hard_ and _soft_ validity.

        Hard validity means that certain things will always be true, and anything that would make them false fails.
        If you take Profession - Journeyman, it depends on Profession - Apprentice, so you can't remove Apprentice
        as long as you have Journeyman.

        Soft validity means that things must _eventually_ be true. You can't add a new Advanced Power if you don't
        have a slot for it, but if you suddenly find yourself with fewer Advanced Powers than you have slots, the
        response is not "you can't do that, abort mutation", but rather "OK, but now you need to pick a power to remove."
        For soft validitiy, see the `issues` method below.

        In general, hard validity is intended to be checked every time you do anything to the character, and if it fails,
        the thing did not happen to the character. If a character ends up persisted in a hard-invalid state and you can't
        fix it in one step, you may need an admin to fix it. (Alternatively, the app can launch your character in "recovery mode",
        and treat hard validation failures as soft until corrected). Soft validity is checked when you try to register for
        an event (or later, when logistics goes to print sheets).
        """
        if self.paid_ranks <= 0:
            # If we don't have the feature purchased but the controller exists anyway, that's fine.
            # No need to validate.
            # Note that this means a feature can be granted without needing to meet its prerequisites.
            return Decision.OK
        # By default, the only validation needed is that the feature's requirements are still met.
        if not (rd := self.meets_requirements):
            # TODO: Nice rendering for the actual requirements issue would be nice, but for now, just
            # identify the feature that has been offended.
            return rd
        return Decision.OK

    def issues(self) -> list[base_models.Issue] | None:
        """Reports issues with the feature (aka, soft validation).

        Unlike validation, the presence of an issue is exepcted to only
        be _eventually_ solved (generally before registration).

        Plot/logistics might also be able to waive a particular issue if it suits their needs.
        """
        issues: list[base_models.Issue] = []
        if self.value > 0:
            if sr := self.definition.soft_requires:
                if not (rd := self.character.meets_requirements(sr)):
                    issues.append(
                        base_models.Issue(
                            issue_code="soft-requirements-not-met",
                            feature_id=self.full_id,
                            reason=rd.reason,
                        )
                    )
        return issues

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
    def id(self) -> str: ...

    @abstractproperty
    def name(self) -> str: ...

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

    def issues(self) -> list[base_models.Issue] | None:
        return None

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
        if (attr_value := getattr(controller, attr.property_id, None)) is not None:
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
    def sheet_type(self) -> Type[base_models.CharacterModel]: ...

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
        model = self.sheet_type(**updated_data)
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
