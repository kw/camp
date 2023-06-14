from __future__ import annotations

from functools import cached_property
from typing import Type

from .. import base_engine
from . import defs
from . import models
from .controllers import character_controller


class TempestEngine(base_engine.Engine):
    ruleset: defs.Ruleset
    sheet_type = models.CharacterModel

    @property
    def character_controller(self) -> Type[base_engine.CharacterController]:
        return character_controller.TempestCharacter

    @cached_property
    def class_defs(self) -> dict[str, defs.ClassDef]:
        return {
            k: f for (k, f) in self.feature_defs.items() if isinstance(f, defs.ClassDef)
        }

    @cached_property
    def skill_defs(self) -> dict[str, defs.SkillDef]:
        return {
            k: f for (k, f) in self.feature_defs.items() if isinstance(f, defs.SkillDef)
        }


class AttributeController(base_engine.AttributeController):
    character: character_controller.TempestCharacter

    def __init__(self, prop_id: str, character: character_controller.TempestCharacter):
        super().__init__(prop_id, character)

    @property
    def value(self):
        return sum(p.grants for p in self._propagation_data.values())
