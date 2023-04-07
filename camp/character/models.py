from __future__ import annotations

from typing import cast

from django.conf import settings as _settings
from django.contrib.auth import get_user_model
from django.db import models
from rules.contrib.models import RulesModel

import camp.engine.loader
import camp.engine.rules.base_engine
import camp.engine.rules.base_models
import camp.game.models
from camp.engine.rules.base_engine import Engine

User = get_user_model()


class Character(RulesModel):
    name: str = models.CharField(max_length=255, help_text="Name of the character.")
    player_name: str = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Name of the player, if different from the owner. Typically used when managing characters for family members.",
    )
    owner: User = models.ForeignKey(
        _settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="characters",
        help_text="The user who owns this character. Not necessarily the character's portrayer.",
    )
    chapter: camp.game.models.Chapter = models.ForeignKey(
        camp.game.models.Chapter,
        on_delete=models.PROTECT,
        related_name="characters",
        help_text="The chapter this character belongs to.",
    )

    @property
    def primary_sheet(self) -> Sheet:
        if first := self.sheets.filter(primary=True).first():
            return first
        if first := self.sheets.first():
            first.primary = True
            first.save()
            return first
        if ruleset := self.chapter.game.rulesets.filter(enabled=True).first():
            engine: Engine = cast(Engine, ruleset.engine)
            sheet = Sheet.objects.create(
                character=self,
                ruleset=ruleset,
                primary=True,
            )
            metadata = camp.engine.rules.base_models.CharacterMetadata(
                id=self.id,
                character_name=self.name,
                player_id=self.owner.id,
                player_name=self.player_name or self.owner.username,
            )
            sheet.controller = engine.new_character(id=sheet.id, metadata=metadata)
            sheet.save()
            return sheet
        raise ValueError(f"No enabled ruleset found for chapter {self.chapter.id}.")

    @property
    def secondary_sheets(self) -> models.QuerySet[Sheet]:
        return self.sheets.filter(primary=False)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Character {self.id} {self.name}>"


class Sheet(RulesModel):
    character: Character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="sheets",
        help_text="The character this sheet is for.",
    )
    ruleset: camp.game.models.Ruleset = models.ForeignKey(
        camp.game.models.Ruleset,
        on_delete=models.PROTECT,
        related_name="sheets",
        help_text="The ruleset this sheet is intended to use.",
    )
    primary: bool = models.BooleanField(
        default=False,
        help_text="Whether this sheet is the primary sheet for the character.",
    )
    label: str = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=(
            "The label to use for this sheet, if it is not the primary sheet. "
            "Non-primary sheets are typically medical reforges, build-downs for "
            "use in other chapters, test sheets, etc."
        ),
    )
    data: dict = models.JSONField(
        default=dict,
        help_text="The data for this sheet, in the format expected by the ruleset.",
    )
    _controller: camp.engine.rules.base_engine.CharacterController | None = None

    @property
    def controller(self) -> camp.engine.rules.base_engine.CharacterController:
        if self._controller is None:
            self._controller = self.ruleset.engine.load_character(self.data)
        return self._controller

    @controller.setter
    def controller(self, value: camp.engine.rules.base_engine.CharacterController):
        self._controller = value
        self.data = value.dump_dict()

    def save(self, *args, **kwargs) -> None:
        if self._controller is not None and self._controller.mutated:
            self.data = self._controller.dump_dict()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.label:
            return f"{self.character} [{self.label}]"
        return str(self.character)

    def __repr__(self) -> str:
        return f"<Sheet {self.id} {self.character} [{self.label}] {'(primary)' if self.primary else ''}>"
