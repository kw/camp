from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from abc import abstractproperty
from dataclasses import dataclass
from functools import cached_property
from functools import total_ordering
from typing import Any
from typing import Iterable
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
        data = dump_dict(self.model, exclude_unset=False)
        if not isinstance(data, dict):
            pass
        return data

    def dump_model(self) -> base_models.CharacterModel:
        """Returns a copy of the current model."""
        return self.model.copy(deep=True)

    def display_name(self, id: str) -> str:
        """Returns the display name of the given feature."""
        if id in self.ruleset.display_names:
            return self.ruleset.display_names[id]
        if id in self.ruleset.features:
            return self.ruleset.features[id].name
        if id in self.ruleset.attribute_map:
            return self.ruleset.attribute_map[id].name
        return id.replace("_", " ").title()

    def list_features(
        self, type: str | None = None, taken: bool = True, available: bool = True
    ) -> Iterable[BaseFeatureController]:
        """List all features of the given type."""
        if taken:
            for id, fc in self.features.items():
                if type and fc.definition.type != type:
                    continue
                if available and not fc.can_increase():
                    continue
                yield fc
        else:
            for id, definition in self.ruleset.features.items():
                if id in self.features:
                    continue
                if type and definition.type != type:
                    continue
                fc = self.feature_controller(id)
                if available and not fc.can_increase():
                    continue
                yield fc

    @abstractmethod
    def clear_caches(self):
        """Clear any cached data that might need to be recomputed upon mutating the character model."""

    def reconcile(self):
        """Perform any necessary reconciliation of the character model."""
        for feat in list(self.features.values()):
            feat.reconcile()

    def apply(self, mutation: base_models.Mutation | str) -> Decision:
        rd: Decision
        if isinstance(mutation, str):
            mutation = base_models.RankMutation.parse(mutation)
        try:
            match mutation:
                case base_models.RankMutation():
                    rd = self.purchase(mutation)
                case _:
                    rd = Decision(
                        success=False, reason=f"Mutation {mutation} unsupported."
                    )
        except AttributeError:
            raise
        except Exception as exc:
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
        """Check whether the character has _any_ property (feature, attribute, etc) with the given name.

        The base implementation only knows how to check for attributes. Checking for features
        must be added by implementations.
        """
        expr = base_models.PropExpression.parse(expr)
        return expr.prop in self.engine.attribute_map

    @abstractmethod
    def controller(self, id: str) -> PropertyController:
        """Returns the controller (property, attribute, feature, etc) with the given id."""

    def feature_controller(self, id: str) -> BaseFeatureController:
        controller = self.controller(id)
        if isinstance(controller, BaseFeatureController):
            return controller
        raise ValueError(
            f"Expected {id} to be a FeatureController but was {controller}"
        )

    def get_attribute(
        self, expr: str | base_models.PropExpression
    ) -> PropertyController | int | None:
        expr = base_models.PropExpression.parse(expr)
        attr: base_models.Attribute
        if attr := self.engine.attribute_map.get(expr.prop):
            # There are a few different ways an attribute might be stored or computed.
            if hasattr(self, attr.property_name or attr.id):
                attr_value: PropertyController | int = getattr(
                    self, attr.property_name or attr.id
                )
                return attr_value
            else:
                return attr.default_value
        return None

    def get_prop(self, expr: str | base_models.PropExpression) -> int:
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
        if attr := self.get_attribute(expr):
            if isinstance(attr, PropertyController):
                if expr.single is not None:
                    return attr.max_value
                return attr.value
            return attr
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

        legal_values ^= options_excluded

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


@total_ordering
class PropertyController(ABC):
    id: str
    full_id: str
    expression: base_models.PropExpression
    character: CharacterController
    description: str | None
    _propagation_data: dict[str, PropagationData]

    def __init__(self, full_id: str, character: CharacterController):
        self._propagation_data = {}
        self.expression = base_models.PropExpression.parse(full_id)
        self.full_id = full_id
        self.id = self.expression.prop
        self.character = character

    def display_name(self) -> str:
        name = self.character.display_name(self.expression.prop)
        if self.expression.option:
            name += f" [{self.expression.option}]"
        return name

    @abstractproperty
    def value(self) -> int:
        ...

    @property
    def max_value(self) -> int:
        return self.value

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
    @cached_property
    def expr(self) -> base_models.PropExpression:
        return base_models.PropExpression.parse(self.id)

    @cached_property
    def definition(self) -> base_models.BaseFeatureDef:
        return self.character.engine.feature_defs[self.expr.prop]

    @property
    def description(self) -> str | None:
        return self.definition.description

    @property
    def max_ranks(self) -> int:
        if self.definition.ranks == "unlimited":
            # Arbitrarily chosen large int.
            return 101
        return self.definition.ranks

    @property
    def option(self) -> str | None:
        return self.expression.option

    @property
    def option_def(self) -> base_models.OptionDef | None:
        return self.definition.option

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
    def taken_options(self) -> dict[str, int]:
        return {}

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

    def __str__(self) -> str:
        if self.expr.option:
            name = f"{self.definition.name} [{self.expr.option}]"
        else:
            name = f"{self.definition.name}"
        if (
            isinstance(self.definition.ranks, str)
            or self.definition.ranks > 1
            and self.value > 0
        ):
            name += f" x{self.value}"
        return name


class AttributeController(PropertyController):
    @cached_property
    def definition(self) -> base_models.Attribute:
        return self.character.engine.attribute_map[self.id]

    def __str__(self) -> str:
        return f"{self.definition.name}: {self.value}"


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
    grants: int = 0

    def __bool__(self) -> bool:
        return bool(self.grants)
