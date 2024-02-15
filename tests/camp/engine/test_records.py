"""Tests for player/character record calculations."""

from __future__ import annotations

from datetime import date

from camp.engine.rules.tempest.campaign import Campaign
from camp.engine.rules.tempest.campaign import Event
from camp.engine.rules.tempest.records import AwardRecord
from camp.engine.rules.tempest.records import CharacterRecord
from camp.engine.rules.tempest.records import PlayerRecord

GRM = "grimoire"
ARC = "arcanorum"

# This reflects the Season 1 event schedule.
EVENT_HISTORY = [
    Event(chapter=ARC, date=date(2023, 3, 19)),
    Event(chapter=ARC, date=date(2023, 4, 16)),
    Event(chapter=GRM, date=date(2023, 4, 30)),
    Event(chapter=ARC, date=date(2023, 5, 14)),
    Event(chapter=ARC, date=date(2023, 6, 18)),
    Event(chapter=ARC, date=date(2023, 7, 16)),
    Event(chapter=ARC, date=date(2023, 8, 13)),
    Event(chapter=GRM, date=date(2023, 8, 27)),
    Event(chapter=ARC, date=date(2023, 9, 3)),
    Event(chapter=GRM, date=date(2023, 9, 24)),
    Event(chapter=ARC, date=date(2023, 10, 2), xp_value=12),
    Event(chapter=GRM, date=date(2023, 10, 29)),
]
CAMPAIGN = Campaign(name="Tempest Test", start_year=2023).add_events(EVENT_HISTORY)

# An award schedule where a single character goes to all events
AWARDS_SINGLE_ALL = [
    AwardRecord(
        character="Bob",
        date=event.date,
        origin=event.chapter,
        event_xp=event.xp_value,
        event_cp=event.cp_value,
    )
    for event in EVENT_HISTORY
]

# Award schedule where the player went to all Arcanorum events with one character.
AWARDS_ONLY_ARC = [
    AwardRecord(
        character="Bob",
        date=event.date,
        origin=event.chapter,
        event_xp=event.xp_value,
        event_cp=event.cp_value,
    )
    for event in EVENT_HISTORY
    if event.chapter is ARC
]

# Award schedule where the player went to all Grimoire events with one character.
AWARDS_ONLY_GRM = [
    AwardRecord(
        character="Bob",
        date=event.date,
        origin=event.chapter,
        event_xp=event.xp_value,
        event_cp=event.cp_value,
    )
    for event in EVENT_HISTORY
    if event.chapter is GRM
]

# Award schedule where the player went to only even-numbered Arcanorum events.
AWARDS_HALF_ARC = [award for (i, award) in enumerate(AWARDS_ONLY_ARC) if i % 2 == 0]

# Award schedule where the player went to all events, but played a different character in each chapter.
AWARDS_SPLIT_CHARACTER = [
    award.model_copy(update={"character": "Adam" if award.origin == ARC else "Greg"})
    for award in AWARDS_SINGLE_ALL
]

# Award schedule where the player only went to a single day of each Arcanorum event.
AWARDS_DAYGAMER = [
    award.model_copy(update={"event_xp": 4}) for award in AWARDS_ONLY_ARC
]


PLAYER = PlayerRecord(
    user="Test Player",
    characters={
        "Bob": CharacterRecord(id="Bob"),
        "Adam": CharacterRecord(id="Adam"),
        "Greg": CharacterRecord(id="Greg"),
    },
)


def test_awards_single_all():
    """What a dedicated player! They get all the things."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_SINGLE_ALL)
    assert updated.xp == CAMPAIGN.max_xp

    # The character actually played gets all the CP.
    bob = updated.characters["Bob"]
    assert bob.event_cp == CAMPAIGN.max_cp

    # The character attended 4 events over the CP cap (8), so they
    # should have saturated their Bonus CP allowance.
    assert bob.bonus_cp == CAMPAIGN.max_bonus_cp

    # The other characters are at the CP floor, with no bonus.
    for other in updated.characters.values():
        if other is bob:
            continue
        assert other.event_cp == CAMPAIGN.latest_values.floor_cp
        assert other.bonus_cp == 0


def test_awards_arc_only():
    """They only played Arcanorum, no Bonus CP."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_ONLY_ARC)
    assert updated.xp == CAMPAIGN.max_xp

    # The character actually played gets all the CP.
    bob = updated.characters["Bob"]
    assert bob.event_cp == CAMPAIGN.max_cp

    # The character attended no events over the CP cap (8), so they
    # should have zero Bonus CP.
    assert bob.bonus_cp == 0

    # The other characters are at the CP floor, with no bonus.
    for other in updated.characters.values():
        if other is bob:
            continue
        assert other.event_cp == CAMPAIGN.latest_values.floor_cp
        assert other.bonus_cp == 0
