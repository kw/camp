from __future__ import annotations

import logging
from typing import TypeAlias
from typing import cast

from django.conf import settings as _settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db import transaction
from django.urls import reverse
from rules.contrib.models import RulesModel

import camp.engine.loader
import camp.engine.rules.base_engine
import camp.engine.rules.base_models
import camp.game.models
from camp.engine.rules.base_engine import Engine
from camp.engine.rules.base_models import CharacterMetadata
from camp.engine.rules.base_models import Mutation
from camp.engine.rules.base_models import load_mutation
from camp.game.models import game_models

User: TypeAlias = get_user_model()  # type: ignore


class Character(RulesModel):
    name = models.CharField(max_length=255, help_text="Name of the character.")
    game = models.ForeignKey(
        camp.game.models.Game,
        on_delete=models.CASCADE,
        related_name="characters",
        help_text="The game this character belongs to.",
    )
    campaign = models.ForeignKey(
        camp.game.models.Campaign,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="characters",
        help_text="The campaign this character belongs to.",
    )
    player_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Name of the player, if different from the owner. Typically used when managing characters for family members.",
    )
    owner = models.ForeignKey(
        _settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="characters",
        help_text="The user who owns this character. Not necessarily the character's portrayer.",
    )
    discarded_date = models.DateTimeField(null=True, blank=True, default=None)
    discarded_by = models.ForeignKey(
        User, null=True, blank=True, default=None, on_delete=models.SET_NULL
    )

    @property
    def is_discarded(self) -> bool:
        return self.discarded_date is not None

    @property
    def metadata(self) -> CharacterMetadata | None:
        if self.campaign is None:
            return None
        player_data = game_models.PlayerCampaignData.retrieve_model(
            user=self.owner, campaign=self.campaign
        )
        return player_data.record.metadata_for(self.id, self.campaign.record)

    @property
    def primary_sheet(self) -> Sheet:
        if first := self.sheets.filter(primary=True).first():
            return first
        if first := self.sheets.first():
            first.primary = True
            first.save()
            return first
        if ruleset := self.game.rulesets.filter(enabled=True).first():
            engine: Engine = cast(Engine, ruleset.engine)
            sheet = Sheet.objects.create(
                character=self,
                ruleset=ruleset,
                primary=True,
            )
            sheet.controller = engine.new_character(id=sheet.id)
            sheet.save()
            return sheet
        raise ValueError(f"No enabled ruleset found for {self.game}.")

    @property
    def secondary_sheets(self) -> models.QuerySet[Sheet]:
        return self.sheets.filter(primary=False)

    def __str__(self) -> str:
        name = self.name or "[Unnamed]"
        if self.is_discarded:
            return f"{name} (Discarded)"
        return name

    def __repr__(self) -> str:
        return f"<Character {self.id} {self.name}>"

    def get_absolute_url(self):
        return reverse("character-detail", kwargs={"pk": self.pk})

    class Meta:
        rules_permissions = {
            "view": game_models.is_object_owner
            | game_models.is_logistics
            | game_models.is_plot,
            "change": game_models.is_object_owner
            | game_models.is_logistics
            | game_models.is_plot,
            "delete": game_models.is_object_owner | game_models.is_logistics,
            "add": game_models.is_authenticated,
        }


class Sheet(RulesModel):
    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="sheets",
        help_text="The character this sheet is for.",
    )
    ruleset = models.ForeignKey(
        "game.Ruleset",
        on_delete=models.PROTECT,
        related_name="sheets",
        help_text="The ruleset this sheet is intended to use.",
    )
    primary: bool = models.BooleanField(
        default=False,
        help_text="Whether this sheet is the primary sheet for the character.",
    )
    label = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=(
            "The label to use for this sheet, if it is not the primary sheet. "
            "Non-primary sheets are typically medical reforges, build-downs for "
            "use in other chapters, test sheets, etc."
        ),
    )
    data = models.JSONField(
        default=dict,
        help_text="The data for this sheet, in the format expected by the ruleset.",
    )
    _controller: camp.engine.rules.base_engine.CharacterController | None = None

    @property
    def game(self) -> camp.game.models.Game:
        return self.character.game

    @property
    def owner(self) -> User:
        return self.character.owner

    @property
    def controller(self) -> camp.engine.rules.base_engine.CharacterController:
        if self._controller is None:
            metadata = None
            flags = {}
            if self.character.campaign is not None:
                metadata = self.character.metadata
                flags = {"freeplay": False}
            else:  # This is a freeplay character
                flags["freeplay"] = True
            self._controller = self.ruleset.engine.load_character(
                self.data, metadata, flags
            )
        return self._controller

    @controller.setter
    def controller(self, value: camp.engine.rules.base_engine.CharacterController):
        self._controller = value
        self.data = value.dump_dict()

    def save(self, *args, **kwargs) -> None:
        if self._controller is not None and self._controller.mutated:
            self.data = self._controller.dump_dict()
        super().save(*args, **kwargs)

    @property
    def last_undo(self) -> UndoStackEntry | None:
        return self.undo_stack.order_by("-timestamp").first()

    @property
    def last_mutation(self) -> Mutation | None:
        if last := self.last_undo:
            return last.load_mutation()
        return None

    def undo(self) -> Mutation | None:
        with transaction.atomic():
            if not self.undo_available():
                return
            last: UndoStackEntry = self.undo_stack.order_by("-timestamp").first()
            self.data = last.previous_data
            self.save()
            if last.mutation:
                mutation = load_mutation(last.mutation)
            else:
                mutation = None
            last.delete()
            self._controller = None
            return mutation

    def undo_available(self) -> bool:
        return self.undo_stack.exists()

    def __str__(self) -> str:
        if self.label:
            return f"{self.character} [{self.label}]"
        return str(self.character)

    def __repr__(self) -> str:
        return f"<Sheet {self.id} {self.character} [{self.label}] {'(primary)' if self.primary else ''}>"

    class Meta:
        rules_permissions = {
            "view": game_models.is_object_owner
            | game_models.is_logistics
            | game_models.is_plot,
            "change": game_models.is_object_owner
            | game_models.is_logistics
            | game_models.is_plot,
            "delete": game_models.is_object_owner | game_models.is_logistics,
            "add": game_models.is_object_owner | game_models.is_logistics,
        }


class UndoStackEntry(models.Model):
    sheet = models.ForeignKey(
        Sheet, on_delete=models.CASCADE, related_name="undo_stack"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    mutation = models.JSONField(null=True, blank=True)
    previous_data = models.JSONField()

    def load_mutation(self) -> Mutation | None:
        if self.mutation:
            try:
                return load_mutation(self.mutation)
            except Exception:
                logging.exception(
                    "Unable to load undo stack mutation for %s", self.mutation
                )
        return None

    def __str__(self) -> str:
        mutation = self.load_mutation()
        if mutation:
            return (
                f"Undo {self.sheet.controller.describe_mutation(self.load_mutation())}"
            )
        else:
            return "Undo"
