"""Record models, specifically for player, character, and award records.

These models represent the mechanical records associated with a player,
namely their event (and other) award histories and how those awards are
divvied up to characters.

As with the `campaign` module next door, these models are are just for the
award calculation system. Actual player and character information is stored
in other models, and the app will use the values derived from these
models to populate the CharacterMetadata in the character sheet model.

For more details, see:
https://docs.google.com/document/d/1qva8lxQqHIJZ-vl4OWU7cu_9i2uaUc_1AGjQPgHGzNA/edit
"""

from __future__ import annotations

import datetime

from pydantic import Field

from ..base_models import BaseModel
from ..base_models import CharacterMetadata
from .campaign import Campaign


class AwardRecord(BaseModel, frozen=True):
    """Represents awards, normally from events.

    Additionally, bonus CP, purchased SP, and role/class flags can be set here.

    Attributes:
      date: The date this award is associated with. Not necessarily the date someone
        literally pushed a button to award it.
      origin: Descriptive debugging text noting where/who the award came from.
      character: If the award relates to a character, an identifier should appear here.
      needs_character: True if the award needs to be associated with a character.
        If the character is not specified by the awarder, or is not specified in a format
        understood by the web app, the player may be prompted to choose a character for it.
      event_xp: The amount of an event's XP award to assign. The player may gain more or less
        or none of this XP than this due to being ahead of or behind the Campaign Max XP at
        the time of the award.
      event_cp: The amount of Event CP to award to the character associated with this award.
        The character may not actually gain any CP if they're already at their limit for both
        Event CP and Bonus CP.
      bonus_cp: Amount of Bonus CP to award. The awarder should not manually move Event CP here,
        that will be handled automatically if needed. The character may not actually receive any
        Bonus CP if they're already at their limit for the season.
      background_approved: This award marks the character as having an approved background. Even
        if the character receives more than one of these (from separate chapters, say) they still
        only get the credit once.
      player_flags: Arbitrary flags to add to the player. For use in role/class/art access.
      character_flags: Arbitrary flags to add to the character. For use in role/class/art access.
      character_grants: Arbitrary grant strings, like "lore#Nature" or "divine-favor:3" or "lp:2",
        in case plot wants to arbitrarily add or subtract things to or from a character card.
    """

    date: datetime.date
    origin: str | None = None
    character: int | str | None = None
    needs_character: bool = True
    event_xp: int = 0
    event_cp: int = 0
    bonus_cp: int = 0
    background_approved: bool | None = None
    # TODO: Handle the rest of this stuff later
    player_flags: dict[str, int | str | list[int | str]] | None = None
    character_flags: dict[str, int | str | list[int | str]] | None = None
    character_grants: list[str] | None = None


class CharacterRecord(BaseModel, frozen=True):
    """Represents a character record.

    Due to the existence of pre-CMA records, a character record may not initially
    be associated with a full character model.

    Attributes:
      id: The character ID, or some debugging value if unknown.

    """

    id: int | str | None = None
    awards: list[AwardRecord] = Field(default_factory=list)
    event_cp: int = 0
    bonus_cp: int = 0
    background_approved: bool = False


class PlayerRecord(BaseModel, frozen=True):
    """Represents player event and award attendance.

    Due to the existence of a pre-CMA records, a player record may not initially
    be associated with an actual web app user/membership.

    Attributes:
      user: If populated, either the username of the player or something
        descriptive. This is only used for debugging purposes.
      xp: Amount of XP the player has earned.
      awards: List of all awards associated with this player.
        Any awards meant for a specific character will also be copied into
        that character's awards list.
      characters: The set of all character records associated with this player.
      last_campaign_date: The date of the most recent campaign event at
        the time this player record was last updated.
    """

    user: str | None = None
    xp: int = 0
    awards: list[AwardRecord] = Field(default_factory=list)
    characters: dict[str | int, CharacterRecord] = Field(default_factory=list)
    last_campaign_date: datetime.date | None = None

    def update(
        self, campaign: Campaign, new_awards: list[AwardRecord] | None = None
    ) -> PlayerRecord:
        """Process new awards and any campaign-level changes to update player/character records.

        These records may change even in the absence of new awards when the Campaign XP/CP Floors move.
        """
        # TODO: Implement it.
        return self

    def metadata_for(self, character_id: int | str) -> CharacterMetadata:
        """Produce character metadata for the indicated character."""
        raise NotImplementedError
