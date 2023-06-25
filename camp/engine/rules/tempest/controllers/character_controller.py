from __future__ import annotations

from functools import cached_property

from camp.engine.rules import base_engine
from camp.engine.rules.base_models import ChoiceMutation
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.base_models import RankMutation
from camp.engine.rules.decision import Decision

from .. import defs
from .. import engine  # noqa: F401
from .. import models
from . import attribute_controllers
from . import cantrip_controller
from . import class_controller
from . import feature_controller
from . import flaw_controller
from . import spell_controller
from . import spellbook_controller
from . import subfeature_controller

_DISPLAY_PRIORITIES = {
    "class": 0,
    "breed": 1,
    "flaw": 2,
    "perk": 3,
    "skill": 4,
    "cantrip": 5,
    "utility": 6,
    "spell": 7,
    "power": 8,
}


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
        return self.ruleset.xp_table.evaluate(self.xp)

    @xp_level.setter
    def xp_level(self, value):
        """Set the XP level to a specific level.

        This is a convenience method primarily for testing purposes. If an XP
        level is manually set, the copy of the metadata attached to the sheet will be
        overwritten with the needed XP. Characters in a real app will likely have
        their source of metadata truth stored elsewhere and applied on load, so
        persisting this change will not do what you want for such characters.
        """
        self.model.metadata.awards["xp"] = self.ruleset.xp_table.reverse_lookup(value)
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
    def spikes(self) -> int:
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
            if controller.is_archetype:
                return controller
        return None

    @property
    def basic_classes(self) -> int:
        return sum(1 for c in self.classes if c.class_type == "basic")

    @property
    def starting_class(self) -> class_controller.ClassController | None:
        for controller in self.classes:
            if controller.is_starting:
                return controller
        return None

    def display_priority(self, feature_type: str) -> int:
        return _DISPLAY_PRIORITIES.get(feature_type, 99)

    @property
    def features(self) -> dict[str, feature_controller.FeatureController]:
        if self._features:
            return self._features
        self._features = {id: self._new_controller(id) for id in self.model.features}
        return self._features

    @property
    def classes(self) -> list[class_controller.ClassController]:
        """List of the character's class controllers."""
        classes = [
            feat
            for feat in list(self.features.values())
            if feat.feature_type == "class" and feat.value > 0
        ]
        classes.sort(key=lambda c: c.value, reverse=True)
        return classes

    @property
    def archetype_legal_classes(self) -> list(class_controller.ClassController):
        """List of classes that are legal to be the character's archetype."""
        classes = self.classes
        max_level = max([c.value for c in classes], default=0)
        return [c for c in classes if c.value == max_level]

    @property
    def is_multiclass(self) -> bool:
        return len(self.classes) > 1

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

    @property
    def cantrips(self) -> dict[str, cantrip_controller.CantripController]:
        return [
            feat
            for feat in self.features.values()
            if isinstance(feat, cantrip_controller.CantripController)
        ]

    @property
    def spells(self) -> list[spell_controller.SpellController]:
        return [
            feat
            for feat in self.features.values()
            if isinstance(feat, spell_controller.SpellController)
        ]

    def can_purchase(self, entry: RankMutation | str) -> Decision:
        if not isinstance(entry, RankMutation):
            entry = RankMutation.parse(entry)
        if controller := self.feature_controller(entry.expression):
            if entry.ranks > 0:
                return controller.can_increase(entry.ranks)
            elif entry.ranks < 0:
                return controller.can_decrease(-entry.ranks)
        return Decision(
            success=False, reason=f"Purchase not implemented: {entry.expression}"
        )

    def purchase(self, entry: RankMutation) -> Decision:
        if controller := self.feature_controller(entry.expression):
            if entry.ranks > 0:
                return controller.increase(entry.ranks)
            elif entry.ranks < 0:
                return controller.decrease(-entry.ranks)
        return Decision(
            success=False, reason=f"Purchase not implemented: {entry.expression}"
        )

    def choose(self, entry: ChoiceMutation) -> Decision:
        if controller := self.feature_controller(entry.id):
            if entry.remove:
                return controller.unchoose(entry.choice, entry.value)
            return controller.choose(entry.choice, entry.value)
        return Decision(success=False, reason=f"Unknown feature {entry.id}")

    def has_prop(self, expr: str | PropExpression) -> bool:
        """Check whether the character has _any_ property (feature, attribute, etc) with the given name.

        The base implementation only knows how to check for attributes. Checking for features
        must be added by implementations.
        """
        expr = PropExpression.parse(expr)
        if super().has_prop(expr):
            return True
        if controller := self.controller(expr):
            return controller.value > 0
        return False

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
        if controller := self.feature_controller(PropExpression.parse(id)):
            return controller.taken_options
        return super().get_options(id)

    @cached_property
    def martial(self) -> spellbook_controller.SphereAttribute:
        return spellbook_controller.SphereAttribute("martial", self)

    @cached_property
    def caster(self) -> base_engine.AttributeController:
        return attribute_controllers.SumAttribute("caster", self, "class", "caster")

    @cached_property
    def arcane(self) -> spellbook_controller.SphereAttribute:
        return spellbook_controller.SphereAttribute("arcane", self)

    @cached_property
    def divine(self) -> spellbook_controller.SphereAttribute:
        return spellbook_controller.SphereAttribute("divine", self)

    @cached_property
    def spellbooks(self) -> list[spellbook_controller.SpellbookController]:
        return [self.arcane.spellbook, self.divine.spellbook]

    def _new_controller(self, id: str) -> feature_controller.FeatureController:
        match self._feature_type(id):
            case None:
                raise ValueError(f"Unknown feature {id}")
            case "class":
                return class_controller.ClassController(id, self)
            case "flaw":
                return flaw_controller.FlawController(id, self)
            case "subfeature":
                return subfeature_controller.SubfeatureController(id, self)
            case "skill":
                return feature_controller.SkillController(id, self)
            case "perk":
                return feature_controller.PerkController(id, self)
            case "cantrip":
                return cantrip_controller.CantripController(id, self)
            case "spell":
                return spell_controller.SpellController(id, self)
            case _:
                return feature_controller.FeatureController(id, self)

    def feature_controller(
        self, expr: PropExpression | str
    ) -> feature_controller.FeatureController:
        expr = PropExpression.parse(expr)
        # If this is already on the sheet, fetch its controller
        if controller := self.features.get(expr.full_id):
            return controller
        # Otherwise, create a controller and for it.
        return self._new_controller(expr.full_id)

    def describe_expr(self, expr: str | PropExpression) -> str:
        expr = PropExpression.parse(expr)
        name = self.display_name(expr.prop)
        if expr.option:
            name += f" ({expr.option})"
        if expr.attribute:
            name += f" {expr.attribute}"
        if expr.slot:
            name += f" [{expr.slot}]"
        return name

    def clear_caches(self):
        super().clear_caches()
        self._features = {}
