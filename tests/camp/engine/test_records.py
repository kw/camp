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
    Event(chapter=ARC, date=date(2023, 3, 19)),  # Max = 8; 4
    Event(chapter=ARC, date=date(2023, 4, 16)),  # Max = 16; 12
    Event(chapter=GRM, date=date(2023, 4, 30)),  # Max = 16; --
    Event(chapter=ARC, date=date(2023, 5, 14)),  # Max = 24; 20
    Event(chapter=ARC, date=date(2023, 6, 18)),  # Max = 32; 28
    Event(chapter=ARC, date=date(2023, 7, 16)),  # Max = 48; 36
    Event(chapter=ARC, date=date(2023, 8, 13)),  # Max = 56; 44
    Event(chapter=GRM, date=date(2023, 8, 27)),  # Max = 56; --
    Event(chapter=ARC, date=date(2023, 9, 3)),  # Max = 64; 52
    Event(chapter=GRM, date=date(2023, 9, 24)),  # Max = 64; --
    Event(chapter=ARC, date=date(2023, 10, 2), xp_value=12),  # Max = 76; 60
    Event(chapter=GRM, date=date(2023, 10, 29)),  # Max = 76; --
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


def test_no_awards():
    """If you didn't get any awards, that's ok."""
    updated = PLAYER.update(CAMPAIGN)
    assert updated.xp == CAMPAIGN.floor_xp

    for character in updated.characters.values():
        # All characters are at the CP floor, with no bonus.
        assert character.event_cp == CAMPAIGN.floor_cp
        assert character.bonus_cp == 0


def test_awards_single_all():
    """What a dedicated player! They get all the things."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_SINGLE_ALL)
    assert updated.xp == CAMPAIGN.max_xp == 76

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
        assert other.event_cp == CAMPAIGN.floor_cp
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
        assert other.event_cp == CAMPAIGN.floor_cp
        assert other.bonus_cp == 0


def test_awards_grm_only():
    """They only played Grimoire."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_ONLY_GRM)
    # Miraculously, if you played only Grimoire games, I believe
    # you'd still hit Campaign Max XP due to floor hits and doubling.
    assert updated.xp == CAMPAIGN.max_xp

    # The character only went to four games, so they have 4 Event CP.
    # This happens to also be the CP floor.
    bob = updated.characters["Bob"]
    assert bob.event_cp == CAMPAIGN.floor_cp == 4
    assert bob.bonus_cp == 0

    # The other characters are at the CP floor, with no bonus.
    for other in updated.characters.values():
        if other is bob:
            continue
        assert other.event_cp == CAMPAIGN.floor_cp
        assert other.bonus_cp == 0


def test_awards_half_arc():
    """This player went to only even-numbered Arcanorum events."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_HALF_ARC)
    # They don't *quite* get to Max XP, but it's close.
    assert updated.xp == 74

    # Only four events = campaign floor CP
    for character in updated.characters.values():
        # All characters are at the CP floor, with no bonus.
        assert character.event_cp == CAMPAIGN.floor_cp
        assert character.bonus_cp == 0


def test_awards_split():
    """This player went to all events, but with a different character per chapter."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_SPLIT_CHARACTER)
    # All games attended = Max XP
    assert updated.xp == CAMPAIGN.max_xp

    bob = updated.characters["Bob"]  # Went to no games
    adam = updated.characters["Adam"]  # Went to 8 Arc games
    greg = updated.characters["Greg"]  # Went to 4 Grim games

    assert len(bob.awards) == 0
    assert bob.event_cp == CAMPAIGN.floor_cp
    assert bob.bonus_cp == 0

    assert len(adam.awards) == 8
    assert adam.event_cp == CAMPAIGN.max_cp
    assert adam.bonus_cp == 0

    assert len(greg.awards) == 4
    assert greg.event_cp == CAMPAIGN.floor_cp
    assert adam.bonus_cp == 0


def test_awards_daygamer():
    """This player attended a single day (4 XP) from each Arcanorum game."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_DAYGAMER)

    # This player doesn't quite manage to keep up with the Campaign Max XP
    assert updated.xp == 60

    # But Bob went to all the Arc events, so he gets all the CP
    bob = updated.characters["Bob"]
    assert bob.event_cp == CAMPAIGN.max_cp
    assert bob.bonus_cp == 0  # But not Bonus CP.

    # Of course, other characters are on the floor
    for other in updated.characters.values():
        if other is bob:
            continue
        assert other.event_cp == CAMPAIGN.floor_cp
        assert other.bonus_cp == 0
