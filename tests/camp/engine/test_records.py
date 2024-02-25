"""Tests for player/character record calculations."""

from __future__ import annotations

import random
from datetime import date

import pytest

from camp.engine.rules.tempest.campaign import Campaign
from camp.engine.rules.tempest.campaign import Event
from camp.engine.rules.tempest.records import AwardRecord
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
        description=event.chapter,
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
        description=event.chapter,
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
        description=event.chapter,
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
    award.model_copy(
        update={"character": "Adam" if award.description == ARC else "Greg"}
    )
    for award in AWARDS_SINGLE_ALL
]

# Award schedule where the player only went to a single day of each Arcanorum event.
AWARDS_DAYGAMER = [
    award.model_copy(update={"event_xp": 4}) for award in AWARDS_ONLY_ARC
]


PLAYER = PlayerRecord(
    user="Test Player",
)


def test_no_awards():
    """If you didn't get any awards, that's ok."""
    updated = PLAYER.update(CAMPAIGN)
    assert updated.xp == CAMPAIGN.floor_xp

    # No character records present.
    assert len(updated.characters) == 0


def test_awards_single_all():
    """What a dedicated player! They get all the things."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_SINGLE_ALL)
    assert updated.xp == CAMPAIGN.max_xp == 68

    # The character actually played gets all the CP.
    bob = updated.characters["Bob"]
    assert bob.event_cp == CAMPAIGN.max_cp

    # The character attended 4 events over the CP cap (8), so they
    # should have saturated their Bonus CP allowance.
    assert bob.bonus_cp == CAMPAIGN.max_bonus_cp

    # No other character records present.
    assert len(updated.characters) == 1


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

    # No other character records present.
    assert len(updated.characters) == 1


def test_awards_grm_only():
    """They only played Grimoire."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_ONLY_GRM)
    # Miraculously, if you played only Grimoire games, I believe
    # you'd still hit Campaign Max XP due to floor hits and doubling.
    assert updated.xp == CAMPAIGN.max_xp

    # The character only went to four games, so they have 4 Event CP.
    # This happens to also be the CP floor.
    bob = updated.characters["Bob"]
    assert bob.event_cp == 6
    assert bob.bonus_cp == 0

    # No other character records present.
    assert len(updated.characters) == 1


def test_awards_half_arc():
    """This player went to only even-numbered Arcanorum events."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_HALF_ARC)
    # They don't *quite* get to Max XP, but it's close.
    assert updated.xp == 56

    # No other character records present.
    assert len(updated.characters) == 1


def test_awards_split():
    """This player went to all events, but with a different character per chapter."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_SPLIT_CHARACTER)
    # All games attended = Max XP
    assert updated.xp == CAMPAIGN.max_xp

    adam = updated.characters["Adam"]  # Went to 8 Arc games
    greg = updated.characters["Greg"]  # Went to 4 Grim games

    assert adam.event_cp == 8
    assert adam.bonus_cp == 0

    assert greg.event_cp == 6
    assert adam.bonus_cp == 0

    # No other character records present.
    assert len(updated.characters) == 2


def test_awards_daygamer():
    """This player attended a single day (4 XP) from each Arcanorum game."""
    updated = PLAYER.update(CAMPAIGN, AWARDS_DAYGAMER)

    # This player doesn't quite manage to keep up with the Campaign Max XP
    assert updated.xp == 60

    # But Bob went to all the Arc events, so he gets all the CP
    bob = updated.characters["Bob"]
    assert bob.event_cp == CAMPAIGN.max_cp
    assert bob.bonus_cp == 0  # But not Bonus CP.

    # No other character records present.
    assert len(updated.characters) == 1


def test_incremental_updates_all_events():
    """Play out a season incrementally."""
    campaign = Campaign(name="Tempest Test", start_year=2023)
    awards = []
    player = PLAYER
    for event in EVENT_HISTORY:
        new_award = AwardRecord(
            date=event.date,
            description=event.chapter,
            character="Bob",
            event_xp=event.xp_value,
            event_cp=event.cp_value,
        )
        awards.append(new_award)
        campaign = campaign.add_events([event])
        player = player.update(campaign, [new_award])

    all_at_once_player = PLAYER.update(campaign, awards)

    assert player.xp == campaign.max_xp == 68
    assert player.characters["Bob"].event_cp == 8
    assert player.characters["Bob"].bonus_cp == 3

    assert campaign == CAMPAIGN
    assert player == all_at_once_player


def test_incremental_updates_daygaming():
    """Play out a season incrementally, but only daygame Arcanorum."""
    campaign = Campaign(name="Tempest Test", start_year=2023)
    awards = []
    player = PLAYER
    for event in EVENT_HISTORY:
        campaign = campaign.add_events([event])
        if event.chapter == ARC:
            new_award = AwardRecord(
                date=event.date,
                description=event.chapter,
                character="Bob",
                event_xp=4,
                event_cp=event.cp_value,
            )
            awards.append(new_award)
            player = player.update(campaign, [new_award])
        else:
            player = player.update(campaign)

    all_at_once_player = PLAYER.update(campaign, awards)

    assert campaign == CAMPAIGN
    assert player == all_at_once_player


@pytest.mark.parametrize(
    "name,awards",
    [
        ("single_all", AWARDS_SINGLE_ALL),
        ("daygamer", AWARDS_DAYGAMER),
        ("half_arc", AWARDS_HALF_ARC),
        ("only_arc", AWARDS_ONLY_ARC),
        ("only_grm", AWARDS_ONLY_GRM),
        ("split_char", AWARDS_SPLIT_CHARACTER),
    ],
)
def test_incremental_shuffled_awards(name, awards):
    """What if we incrementally process awards, but they're out of order?

    This test shuffles the award order and feeds those incrementally to the
    updater, then verifies the result is the same as just feeding them all at once.

    The shuffling is deterministic for each sub-test. All the different award scenarios are tested.
    """
    awards = awards.copy()
    random.seed(0)
    random.shuffle(awards)
    player = PLAYER
    for award in awards:
        player = player.update(CAMPAIGN, [award])

    all_at_once_player = PLAYER.update(CAMPAIGN, awards)

    assert player == all_at_once_player


def test_backstory_approval():
    """We can set or unset a backstory flag."""

    approved_player = PLAYER.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2023, 3, 3),
                character="Fred",
                backstory_approved=True,
            )
        ],
    )

    assert approved_player.characters["Fred"].backstory_approved

    revoked_player = approved_player.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2023, 3, 4),
                character="Fred",
                backstory_approved=False,
            )
        ],
    )

    assert not revoked_player.characters["Fred"].backstory_approved


def test_player_flags():
    """Player flags work a bit like environment variables.

    Setting them to anything replaces the previous value.
    Setting the flag to None clears it.
    """
    # Initially setting player flags works.
    player = PLAYER.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2024, 1, 1),
                player_flags={
                    "FOO": "bar",
                    "BAZ": 42,
                    "things": ["stuff", 3, "10"],
                },
            )
        ],
    )

    assert player.flags == {
        "FOO": "bar",
        "BAZ": 42,
        "things": ["stuff", 3, "10"],
    }

    # Updating and deleting flags works.
    player = player.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2024, 1, 2),
                player_flags={
                    "FOO": None,
                    "BAZ": "forty two",
                },
            )
        ],
    )

    assert player.flags == {
        "BAZ": "forty two",
        "things": ["stuff", 3, "10"],
    }


def test_character_flags():
    """Character flags work a bit like environment variables.

    Setting them to anything replaces the previous value.
    Setting the flag to None clears it.
    """
    # Initially setting character flags works.
    player = PLAYER.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2024, 1, 1),
                character="Eve",
                character_flags={
                    "FOO": "bar",
                    "BAZ": 42,
                    "things": ["stuff", 3, "10"],
                },
            )
        ],
    )

    assert player.characters["Eve"].flags == {
        "FOO": "bar",
        "BAZ": 42,
        "things": ["stuff", 3, "10"],
    }

    # Updating and deleting flags works.
    player = player.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2024, 1, 2),
                character="Eve",
                character_flags={
                    "FOO": None,
                    "BAZ": "forty two",
                },
            )
        ],
    )

    assert player.characters["Eve"].flags == {
        "BAZ": "forty two",
        "things": ["stuff", 3, "10"],
    }


def test_character_grants():
    """All grants awarded to a character are recorded."""
    player = PLAYER.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2024, 1, 1),
                character="Eve",
                character_grants=["divine_favor:3", "spoons"],
            )
        ],
    )

    assert player.characters["Eve"].grants == ["divine_favor:3", "spoons"]

    player = player.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2024, 1, 2),
                character="Eve",
                character_grants=["fighter:1", "lore#Soup"],
            )
        ],
    )

    assert player.characters["Eve"].grants == [
        "divine_favor:3",
        "spoons",
        "fighter:1",
        "lore#Soup",
    ]

    # Due to strict date handling, if an award is added in the past, the list will be in date order.
    player = player.update(
        CAMPAIGN,
        [
            AwardRecord(
                date=date(2023, 12, 25),
                character="Eve",
                character_grants=["patron"],
            )
        ],
    )

    assert player.characters["Eve"].grants == [
        "patron",
        "divine_favor:3",
        "spoons",
        "fighter:1",
        "lore#Soup",
    ]
