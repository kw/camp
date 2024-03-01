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
from enum import Enum

from pydantic import BaseModel
from pydantic import Field
from pydantic import TypeAdapter
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from ..base_models import CharacterMetadata
from ..base_models import FlagValues
from .campaign import CampaignRecord
from .campaign import CampaignValues


class AwardCategory(str, Enum):
    UNKNOWN = "unknown"  # Not specified.
    EVENT = "event"  # This is normal event credit.
    NPC_SHIFT = "npc-shift"  # Awards for NPC shifts, on top of normal event awards.
    DONATION = "donation"  # Awards related to fundraisers, prop donation, etc.
    STAFF_ROLE = "staff-role"  # Awards related to beng a member of staff.
    POINT_PURCHASE = (
        "point-purchase"  # Awards purchased using Service Points or equivalent.
    )


class AwardRecord(BaseModel, frozen=True):
    """Represents awards, normally from events.

    Additionally, bonus CP, purchased SP, and role/class flags can be set here.

    Attributes:
      date: The date this award is associated with. Not necessarily the date someone
        literally pushed a button to award it.
      source_id: An identifier indicating an object in an external data model associated
        with this award. The specific type of source may depend on the category (below).
        This may be used in cases where, for example, the award for a specific event needs
        to be revised, which first requires removing the previous award data.
      category: The type of inciting incident associated with this award. For example, the standard
        XP/CP awards for an event (whether you PC or NPC it) have the EVENT category, with
        the event's ID as the source_id. If you also took an NPC Shift and received some reward
        because of it, that would have the NPC_SHIFT category, and the source_id would also be
        the same event.
      description: Descriptive text noting where/who the award came from for display purposes.
      character: If the award relates to a character, an identifier should appear here.
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
      event_played: If true, increases the character's "events played" counter. Normally only true
        on PC event awards. Certain rules interact with this: you can freely rewrite your character
        until a character's second game, certain flags may allow specific changes until the played
        counter ticks, and the undo stack can't cross a played events boundary.
      player_flags: Arbitrary flags to add to the player. For use in role/class/art access.
      character_flags: Arbitrary flags to add to the character. For use in role/class/art access.
      character_grants: Arbitrary grant strings, like "lore#Nature" or "divine-favor:3" or "lp:2",
        in case plot wants to arbitrarily add or subtract things to or from a character card.
    """

    date: datetime.date
    source_id: int | str | None = None
    category: AwardCategory = AwardCategory.UNKNOWN
    description: str | None = None
    character: int | None = None
    event_xp: int = 0
    event_cp: int = 0
    bonus_cp: int = 0
    backstory_approved: bool | None = None
    event_played: bool = False
    player_flags: dict[str, FlagValues | None] | None = None
    character_flags: dict[str, FlagValues | None] | None = None
    character_grants: list[str] | None = None

    def describe(self) -> str:
        if self.description:
            return self.description
        parts = []
        if self.backstory_approved:
            parts.append("Backstory Approval")
        if self.bonus_cp:
            parts.append(f"Bonus CP: {self.bonus_cp}")
        if self.event_xp or self.event_cp:
            parts.append(f"Event: {self.event_xp} XP + {self.event_cp} CP")
        if self.character_flags or self.player_flags:
            parts.append("Secret Flags")
        if parts:
            return ", ".join(parts)
        return "Unknown"

    @property
    def needs_character(self) -> bool:
        """True if a player or logistics needs to associated a character with this record."""
        if not self.character:
            # We need a character assigned if any of the following fields is set:
            return (
                self.event_cp != 0
                or self.bonus_cp != 0
                or self.backstory_approved is not None
                or self.character_flags
                or self.character_grants
                or self.event_played
            )
        return False


class CharacterRecord(BaseModel, frozen=True):
    """Represents a character record.

    Due to the existence of pre-CMA records, a character record may not initially
    be associated with a full character model.

    It is worth mentioning that a character record should only exist for a character
    once they have received some sort of award, whether it's an event award, backstory CP,
    or some sort of SP purchase. Characters with no records exist just fine, but remain
    in an eternal "new character" state until they've received some sort of award.

    Attributes:
      id: The character ID, or some debugging value if unknown.
      event_cp: Amount of Event CP earned by this character (or received as floor CP)
      bonus_cp: Amount of Bonus CP assigned to this character.
      backstory_approved: Flags that this character should receive +2 CP due to an approved backstory.
      events_played: Number of events attended as a PC.
      last_played: Last date when this character was used as a PC.
      flags: Dictionary of flag values awarded to this character in particular. These may override player-level flags.
        Examples include advanced class unlock flags, role flags, etc.
      grants: A list of straight-up bonus grants in the same format used by the character sheet engine.
        For example, to grant a character 3 bonus life points from a deal with The Dark, enter "lp:3".
        While it's technically possible to grant bonus CP this way, don't. That's what bonus_cp is for.
    """

    id: int | None = None
    event_cp: int = 0
    bonus_cp: int = 0
    backstory_approved: bool = False
    events_played: int = 0
    last_played: datetime.date | None = None
    flags: dict[str, FlagValues] = Field(default_factory=dict)
    grants: list[str] = Field(default_factory=list)


class PlayerRecord(BaseModel, frozen=True):
    """Represents player event and award attendance.

    Due to the existence of a pre-CMA records, a player record may not initially
    be associated with an actual web app user/membership.

    Attributes:
      user: If populated, either the username of the player or something
        descriptive. This is only used for debugging purposes.
      xp: Amount of XP the player has earned.
      events_played: Number of events attended as a PC.
      last_played: Last date when any character was used as a PC.
      awards: List of all awards associated with this player.
        Any awards meant for a specific character will also be copied into
        that character's awards list.
      characters: The set of all character records associated with this player.
      last_campaign_date: The date of the most recent campaign event at
        the time this player record was last updated.
      flags: Dictionary of flag values assigned to this player. This will be
        propagated to all of the player's characters, which may be appropriate
        for a GoFundMe custom role, culture, or religion unlock or similar.
    """

    user: int | None = None
    xp: int = 0
    events_played: int = 0
    last_played: datetime.date | None = None
    awards: list[AwardRecord] = Field(default_factory=list)
    characters: dict[int, CharacterRecord] = Field(default_factory=dict)
    last_campaign_date: datetime.date | None = None
    flags: dict[str, FlagValues] = Field(default_factory=dict)

    def update(
        self, campaign: CampaignRecord, new_awards: list[AwardRecord] | None = None
    ) -> PlayerRecord:
        """Process new awards and any campaign-level changes to update player/character records.

        These records may change even in the absence of new awards when the Campaign XP/CP Floors move.
        """
        player = self
        # 1. Order all awards by date.
        if new_awards is None:
            new_awards = []
        else:
            new_awards = sorted(new_awards, key=lambda a: a.date)
            if (player.awards and player.awards[-1].date > new_awards[0].date) or (
                player.last_campaign_date
                and new_awards[0].date < player.last_campaign_date
            ):
                # The new awards contain awards that come before previous processing.
                # Since award processing depends on all previous awards and campaign data, we must either:
                # A) Keep the history of award value processing and rewind it, or
                # B) Drop the current values and regenerate.
                # Out-of-order awards are probably not a common occurence and I don't expect
                # the number of awards to reprocess to be problematic, so do B for now.
                new_awards = sorted(player.awards + new_awards, key=lambda a: a.date)
                player = PlayerRecord(user=player.user)

        # 2. Retrieve the Campaign Max Table (Done!)
        #    (But also get some other bits we need)

        xp = player.xp
        player_flags = player.flags.copy()
        player_events_played = player.events_played
        player_last_played = player.last_played
        event_cp = {id: c.event_cp for id, c in player.characters.items()}
        bonus_cp = {id: c.bonus_cp for id, c in player.characters.items()}
        backstory = {id: c.backstory_approved for id, c in player.characters.items()}
        character_flags = {id: c.flags.copy() for id, c in player.characters.items()}
        character_grants = {id: c.grants.copy() for id, c in player.characters.items()}
        character_plays = {id: c.events_played for id, c in player.characters.items()}
        character_last_played = {
            id: c.last_played for id, c in player.characters.items()
        }

        # 3. At each point in the player’s event history:
        for award in new_awards:
            # a. Look up the Campaign Max values at this point in time, as well as the one just before that.
            current = campaign.get_historical_values(award.date)
            prev = campaign.get_historical_values(
                award.date - datetime.timedelta(days=1)
            )
            # b. If the player is below the previous XP floor, set them to the previous XP floor.
            # c. If any of the player’s characters in this campaign are below the previous CP floor, set them to the previous CP floor.
            xp = _constrain(prev, xp, event_cp, bonus_cp)

            if award.event_played:
                player_events_played += 1
                if player_last_played is None or player_last_played < award.date:
                    player_last_played = award.date

            # d. If the award includes XP, award the stated amount if they are at the previous cap,
            #    else award double the stated value.
            if award.event_xp > 0:
                if xp < prev.max_xp:
                    xp = min(xp + 2 * award.event_xp, current.max_xp)
                else:
                    xp = min(xp + award.event_xp, current.max_xp)

            # Track player flags. Flag operations always clobber the previous value,
            # there is no concept of flags combining. Setting a flag to None deletes it.
            if award.player_flags:
                for flag, value in award.player_flags.items():
                    if value is None and flag in player_flags:
                        del player_flags[flag]
                    elif value is None:
                        pass  # Flag isn't present, ignore attempt to delete it.
                    else:
                        player_flags[flag] = value

            if award.character is not None:
                # e. If the award includes XP, award 1 Event CP to the character associated with the
                # event (either the character played, or the one awarded to, if this was an NPC shift).
                # If this would put the character over Max Event CP, instead add it to Bonus CP. If
                # this would put the character over Max Bonus CP, too bad, discard it.
                if award.event_cp:
                    # The character record might not exist; use a default floor CP as the base if so.
                    current_cp = event_cp.get(award.character, prev.floor_cp)
                    current_bonus_cp = bonus_cp.get(award.character, 0)
                    if current_cp < current.max_cp:
                        event_cp[award.character] = current_cp + award.event_cp
                    elif current_bonus_cp < current.max_bonus_cp:
                        bonus_cp[award.character] = current_bonus_cp + award.event_cp

                # f. If the award includes Bonus CP, add it to the Bonus CP if it is not over cap.
                if award.bonus_cp:
                    current_bonus_cp = bonus_cp.get(award.character, 0)
                    if current_bonus_cp < current.max_bonus_cp:
                        bonus_cp[award.character] = current_bonus_cp + 1

                # Track the backstory flag. An award can potentially set or unset the flag.
                if award.backstory_approved is not None:
                    backstory[award.character] = award.backstory_approved

                # Track the event play counter
                if award.event_played:
                    current_events_played = character_plays.get(award.character, 0)
                    current_last_played = character_last_played.get(
                        award.character, award.date
                    )
                    current_events_played += 1
                    if current_last_played < award.date:
                        current_last_played = award.date
                    character_plays[award.character] = current_events_played
                    character_last_played[award.character] = current_last_played

                # Track character flags. These work just like player flags, but for a character.
                # When character metadata is evaluated, a flag on a character overrides that same
                # flag on the player as a whole.
                if award.character_flags:
                    for flag, value in award.character_flags.items():
                        char_flags = character_flags.setdefault(award.character, {})
                        if value is None and flag in char_flags:
                            del char_flags[flag]
                        elif value is None:
                            pass  # Flag isn't present, ignore attempt to delete it.
                        else:
                            char_flags[flag] = value

                # Track character grants. The full list of grants is maintained, even if some grants
                # could otherwise be combined. Some day, we might want to collate these based on
                # the available feature definitions.
                if award.character_grants:
                    grants = character_grants.setdefault(award.character, [])
                    grants.extend(award.character_grants)

        # 4. Whether or not any events occurred, perform floor/max checks.
        xp = _constrain(campaign, xp, event_cp, bonus_cp)

        # Build updated character records.
        new_characters = {}
        all_character_ids = (
            event_cp.keys()
            | bonus_cp.keys()
            | backstory.keys()
            | character_flags.keys()
            | character_grants.keys()
        )
        for id in all_character_ids:
            new_cp = event_cp.get(id, campaign.floor_cp)
            new_bonus_cp = bonus_cp.get(id, 0)
            new_backstory = backstory.get(id, False)
            flags = character_flags.get(id, {})
            grants = character_grants.get(id, [])
            char_events_played = character_plays.get(id, 0)
            char_last_played = character_last_played.get(id, None)

            # If the character record already existed, updated. Otherwise, make it fresh.
            if id in player.characters:
                char = player.characters[id].model_copy(
                    update={
                        "event_cp": new_cp,
                        "bonus_cp": new_bonus_cp,
                        "events_played": char_events_played,
                        "last_played": char_last_played,
                        "backstory_approved": new_backstory,
                        "flags": flags,
                        "grants": grants,
                    }
                )
            else:
                char = CharacterRecord(
                    id=id,
                    event_cp=new_cp,
                    bonus_cp=new_bonus_cp,
                    events_played=char_events_played,
                    last_played=char_last_played,
                    backstory_approved=new_backstory,
                    flags=flags,
                    grants=grants,
                )
            new_characters[id] = char

        return player.model_copy(
            update={
                "xp": xp,
                "events_played": player_events_played,
                "last_played": player_last_played,
                "characters": new_characters,
                "last_campaign_date": campaign.last_event_date,
                "awards": player.awards + new_awards,
                "flags": player_flags,
            }
        )

    def metadata_for(self, character_id: int) -> CharacterMetadata:
        """Produce character metadata for the indicated character."""
        awards = {"xp": self.xp, "event_cp": 0, "bonus_cp": 0, "backstory_cp": 0}
        flags = self.flags.copy()
        events_played = 0
        last_played = None
        if char := self.characters.get(character_id):
            if char.backstory_approved:
                awards["backstory_cp"] = 2
            flags.update(char.flags)
            events_played = char.events_played
            last_played = char.last_played
            awards["event_cp"] = char.event_cp
            awards["bonus_cp"] = char.bonus_cp
        return CharacterMetadata(
            events_played=events_played,
            last_played=last_played,
            awards=awards,
            flags=flags,
        )

    @field_validator("awards")
    @classmethod
    def validate_entries_sorted(
        cls, v: list[AwardRecord], info: ValidationInfo
    ) -> list[AwardRecord]:
        """Enforce that the award list must be sorted by date, otherwise we can't search it."""
        if not v:
            return v
        for i in range(1, len(v)):
            if v[i - 1].date > v[i].date:
                raise ValueError("Entries must be sorted by date")
        return v

    @model_validator(mode="after")
    def validate_last_event_date(self):
        """Enforce that the recorded last event date is populated if any awards are recorded."""
        if self.awards and self.last_campaign_date is None:
            raise ValueError(
                "last_campaign_date must be populated if awards have been integrated."
            )
        return self

    @model_validator(mode="after")
    def validate_character_records(self):
        """A character record exists for every character mentioned in an award."""
        for a in self.awards or []:
            if a.character is not None and a.character not in self.characters:
                raise ValueError(
                    f"Character record for {a.character} not properly initialized."
                )
        return self


def _constrain(
    values: CampaignRecord | CampaignValues,
    xp: int,
    event_cp: dict[int, int],
    bonus_cp: dict[int, int],
) -> int:
    """Constrains the given values based on the given campaign values.

    Returns: The adjusted (if necessary) player XP. The CP dictionaries are mutated.
    """
    xp = min(max(xp, values.floor_xp), values.max_xp)
    for id in event_cp:
        event_cp[id] = min(max(event_cp.get(id, 0), values.floor_cp), values.max_cp)
        bonus_cp[id] = min(bonus_cp.get(id, 0), values.max_bonus_cp)
    return xp


AwardRecordAdapter = TypeAdapter(AwardRecord)
PlayerRecordAdapter = TypeAdapter(PlayerRecord)
