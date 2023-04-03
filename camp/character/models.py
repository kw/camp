from __future__ import annotations

from django.conf import settings as _settings
from django.contrib.auth import get_user_model
from django.db import models
from rules.contrib.models import RulesModel

import camp.engine.loader
import camp.engine.rules.base_engine
import camp.engine.rules.base_models
import camp.game.models

User = get_user_model()


class Character(RulesModel):
    name: str = models.CharField(max_length=255)
    owner: User = models.ForeignKey(
        _settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="characters",
    )
    chapter: camp.game.models.Chapter = models.ForeignKey(
        camp.game.models.Chapter,
        on_delete=models.PROTECT,
        related_name="characters",
    )

    @property
    def primary_sheet(self) -> Sheet:
        if first := self.sheets.filter(primary=True).first():
            return first
        if first := self.sheets.first():
            first.primary = True
            first.save()
            return first
        if ruleset := self.chapter.rulesets.filter(enabled=True).first():
            sheet = Sheet.objects.create(
                character=self,
                ruleset=ruleset,
                primary=True,
            )
            metadata = camp.engine.rules.base_models.CharacterMetadata(
                id=sheet.id,
                character_name=self.name,
                player_id=self.owner.id,
                player_name=self.owner.username,
            )
            sheet.save_character(ruleset.engine.create_character(metadata=metadata))
            return sheet
        raise ValueError(f"No enabled ruleset found for chapter {self.chapter.id}.")


class Sheet(RulesModel):
    character: Character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="sheets",
    )
    ruleset: camp.game.models.Ruleset = models.ForeignKey(
        camp.game.models.Ruleset,
        on_delete=models.PROTECT,
        related_name="sheets",
    )
    primary: bool = models.BooleanField(default=False)
    data: dict = models.JSONField()

    def load_character(self) -> camp.engine.rules.base_engine.CharacterController:
        return self.ruleset.engine.load_character(self.data)

    def save_character(
        self, character: camp.engine.rules.base_engine.CharacterController
    ):
        self.data = character.dump_dict()
        self.save()
