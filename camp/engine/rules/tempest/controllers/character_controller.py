from __future__ import annotations

from functools import cached_property
from typing import Mapping
from typing import cast

from camp.engine import utils
from camp.engine.rules import base_engine
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.base_models import RankMutation
from camp.engine.rules.decision import Decision

from .. import defs
from .. import engine  # noqa: F401
from .. import models
from . import attribute_controllers
from . import class_controller
from . import feature_controller
from . import flaw_controller
from . import subfeature_controller


class TempestCharacter(base_engine.CharacterController):
    model: models.CharacterModel
    engine: engine.TempestEngine
    ruleset: defs.Ruleset
    _features: dict[str, feature_controller.FeatureController] | None = None

    @property
    def xp(self) -> int:
        """Experience points"""
        return self.model.metadata.awards.get("xp", 0)

    @property
    def xp_level(self) -> int:
        """Experience level.

        This is slightly different than character level - XP level is
        the character level that you're entitled to have, but actual
        character level is the sum of class levels you've selected. The
        "Level Up!" (or equivalent) button will appear when character level
        is less than XP Level, but will cause a validation error if character
        level exceeds XP level.
        """
        # TODO: Calculate XP levels past the max in the table.
        return utils.table_lookup(self.ruleset.xp_table, self.xp)

    @xp_level.setter
    def xp_level(self, value):
        """Set the XP level to a specific level.

        This is a convenience method primarily for testing purposes. If an XP
        level is manually set, the copy of the metadata attached to the sheet will be
        overwritten with the needed XP. Characters in a real app will likely have
        their source of metadata truth stored elsewhere and applied on load, so
        persisting this change will not do what you want for such characters.
        """
        self.model.metadata.awards["xp"] = utils.table_reverse_lookup(
            self.ruleset.xp_table, value
        )
        self.mutated = True

    @property
    def base_cp(self) -> int:
        """CP granted by formula from the ruleset.

        By default, this is 1 + 2 * Level.
        """
        return self.ruleset.cp_baseline + (self.ruleset.cp_per_level * self.xp_level)

    @property
    def awarded_cp(self) -> int:
        """CP granted by fiat (backstory writing, etc)."""
        return self.model.metadata.awards.get("cp", 0)

    @awarded_cp.setter
    def awarded_cp(self, value: int) -> None:
        self.model.metadata.awards["cp"] = value
        self.mutated = True

    @property
    def base_lp(self) -> int:
        return self.ruleset.lp.evaluate(self.xp_level)

    @cached_property
    def lp(self) -> attribute_controllers.LifePointController:
        return attribute_controllers.LifePointController("lp", self)

    @property
    def base_spikes(self) -> int:
        return self.ruleset.spikes.evaluate(self.xp_level)

    @property
    def can_respend(self) -> bool:
        """Can the character be freely edited?

        This should be true before the character's first full weekend game, and potentially
        before the second. There may be some other situations where it turns on, such as
        a ritual that allows respend, though many of these may be more specific (e.g. a
        ritual that allows breed options to be edited, or an SP action that allows a single
        class level to be respent). We'll handle those on a case-by-case basis elsewhere.
        """
        # TODO: Actually base this on something
        return True

    @cached_property
    def cp(self) -> attribute_controllers.CharacterPointController:
        return attribute_controllers.CharacterPointController("cp", self)

    @cached_property
    def level(self) -> attribute_controllers.SumAttribute:
        return attribute_controllers.SumAttribute("level", self, "class")

    @property
    def levels_available(self) -> int:
        return self.xp_level - self.level.value

    @property
    def primary_class(self) -> class_controller.ClassController | None:
        for controller in self.classes:
            if controller.is_primary:
                return controller
        return None

    @property
    def starting_class(self) -> class_controller.ClassController | None:
        for controller in self.classes:
            if controller.is_starting:
                return controller
        return None

    @property
    def features(self) -> dict[str, feature_controller.FeatureController]:
        if self._features:
            return self._features
        feats: dict[str, feature_controller.FeatureController] = {}
        for id, model in self.model.features.items():
            controller = self._new_controller_for_type(id)
            feats[id] = controller
        self._features = feats
        return feats

    @property
    def classes(self) -> list[class_controller.ClassController]:
        """List of the character's class controllers."""
        classes = [
            feat
            for (feat) in self.features.values()
            if feat.feature_type == "class" and feat.value > 0
        ]
        classes.sort(key=lambda c: c.value, reverse=True)
        return classes

    @property
    def skills(self) -> list[feature_controller.FeatureController]:
        skills = [
            feat
            for (feat) in self.features.values()
            if feat.feature_type == "skill" and feat.value > 0
        ]
        skills.sort(key=lambda s: s.display_name())
        return skills

    def feature_def(self, feature_id: str) -> defs.FeatureDefinitions | None:
        expr = PropExpression.parse(feature_id)
        return self.ruleset.features.get(expr.prop)

    def _feature_type(self, feature_id: str) -> str | None:
        if feature_def := self.feature_def(feature_id):
            return feature_def.type
        return None

    @property
    def flaws(self) -> dict[str, flaw_controller.FlawController]:
        return {
            id: feat
            for (id, feat) in self.features.items()
            if isinstance(feat, flaw_controller.FlawController)
        }

    def can_purchase(self, entry: RankMutation | str) -> Decision:
        if not isinstance(entry, RankMutation):
            entry = RankMutation.parse(entry)
        if controller := self._controller_for_feature(entry.expression):
            if entry.ranks > 0:
                return controller.can_increase(entry.ranks)
            elif entry.ranks < 0:
                return controller.can_decrease(-entry.ranks)
        return Decision(
            success=False, reason=f"Purchase not implemented: {entry.expression}"
        )

    def purchase(self, entry: RankMutation) -> Decision:
        if controller := self._controller_for_feature(entry.expression):
            if entry.ranks > 0:
                return controller.increase(entry.ranks)
            elif entry.ranks < 0:
                return controller.decrease(-entry.ranks)
        return Decision(
            success=False, reason=f"Purchase not implemented: {entry.expression}"
        )

    def has_prop(self, expr: str | PropExpression) -> bool:
        """Check whether the character has _any_ property (feature, attribute, etc) with the given name.

        The base implementation only knows how to check for attributes. Checking for features
        must be added by implementations.
        """
        expr = PropExpression.parse(expr)
        if controller := self._controller_for_feature(expr):
            return controller.value > 0
        return super().has_prop(expr)

    def get_prop(self, id: str | PropExpression) -> int:
        expr = PropExpression.parse(id)
        if controller := self._controller_for_property(expr):
            if expr.single is not None:
                return controller.max_value
            return controller.value
        return super().get_prop(expr)

    def get_choice_def(self, id: str | PropExpression) -> defs.ChoiceDef | None:
        expr = PropExpression.parse(id)
        if feat := self.ruleset.features.get(expr.prop):
            return feat.choices.get(expr.choice)
        return None

    def has_choice(self, id: str) -> bool:
        expr = PropExpression.parse(id)
        if not expr.choice:
            raise ValueError(f"ID {id} does not name a choice.")
        # To have a choice, the character must both have the named feature (including option, if present)
        # and the feature must actually define a choice with that ID.
        return self.has_prop(expr.full_id) and self.get_choice_def(id)

    def get_options(self, id: str) -> dict[str, int]:
        if controller := self._controller_for_feature(PropExpression.parse(id)):
            return controller.taken_options
        return super().get_options(id)

    def controllers_for_type(
        self, feature_type: str
    ) -> Mapping[str, feature_controller.FeatureController]:
        return {
            id: feat
            for (id, feat) in self.features.items()
            if feat.feature_type == feature_type
        }

    @cached_property
    def martial(self) -> base_engine.AttributeController:
        return attribute_controllers.SumAttribute("martial", self, "class", "martial")

    @cached_property
    def caster(self) -> base_engine.AttributeController:
        return attribute_controllers.SumAttribute("caster", self, "class", "caster")

    @cached_property
    def arcane(self) -> base_engine.AttributeController:
        return attribute_controllers.SumAttribute("arcane", self, "class", "arcane")

    @cached_property
    def divine(self) -> base_engine.AttributeController:
        return attribute_controllers.SumAttribute("divine", self, "class", "divine")

    def _new_controller_for_type(self, id: str) -> feature_controller.FeatureController:
        match self._feature_type(id):
            case "class":
                return class_controller.ClassController(id, self)
            case "flaw":
                return flaw_controller.FlawController(id, self)
            case "subfeature":
                return subfeature_controller.SubfeatureController(id, self)
            case _:
                return feature_controller.FeatureController(id, self)

    def _controller_for_feature(
        self, expr: PropExpression | str, create: bool = True
    ) -> feature_controller.FeatureController | None:
        if isinstance(expr, str):
            expr = PropExpression.parse(expr)
        # Figure out what kind of feature this is. Or if it even is one.
        if not (feature_def := self.ruleset.features.get(expr.prop)):
            return None
        # If this skill is already on the sheet, fetch its controller
        if (controller_dict := self.controllers_for_type(feature_def.type)) and (
            controller := controller_dict.get(expr.full_id)
        ) is not None:
            return controller
        # Otherwise, create a controller and ask it.
        if create:
            return self._new_controller_for_type(expr.full_id)
        return None

    def _controller_for_property(
        self, expr: PropExpression | str, create: bool = True
    ) -> base_engine.PropertyController | None:
        if isinstance(expr, str):
            expr = PropExpression.parse(expr)
        if expr.prop in self.ruleset.features:
            return self._controller_for_feature(expr, create=create)
        elif expr.prop in self.ruleset.attribute_map:
            controller = self.get_attribute(expr)
            if isinstance(controller, base_engine.PropertyController):
                return controller
        return None

    def controller(self, id) -> base_engine.PropertyController:
        try:
            c = self._controller_for_property(id)
        except NotImplementedError:
            raise ValueError(f"Controller not yet implemented for {id}")
        if c:
            return c
        raise ValueError(f"Can't find property controller for {id}")

    def feature_controller(self, id: str) -> feature_controller.FeatureController:
        return cast(
            feature_controller.FeatureController, super().feature_controller(id)
        )

    def clear_caches(self):
        super().clear_caches()
        self._features = {}
