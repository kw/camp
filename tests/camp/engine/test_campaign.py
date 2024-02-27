"""Test computations for Campaign Maximum value calculations."""

from __future__ import annotations

from datetime import date

import pytest

from camp.engine.rules.tempest.campaign import DATE_KEY
from camp.engine.rules.tempest.campaign import CampaignRecord
from camp.engine.rules.tempest.campaign import CampaignValues
from camp.engine.rules.tempest.campaign import EventRecord

# Create some test data based on actual event history, plus some future stuff.

GRM = "grimoire"
ARC = "arcanorum"

# Note that the event history isn't presented in any particular order.
EVENT_HISTORY = [
    EventRecord(chapter=GRM, date=date(2023, 4, 30)),
    EventRecord(chapter=GRM, date=date(2023, 8, 27)),
    EventRecord(chapter=GRM, date=date(2023, 9, 24)),
    EventRecord(chapter=GRM, date=date(2023, 10, 29)),
    EventRecord(chapter=ARC, date=date(2023, 4, 16)),
    EventRecord(chapter=ARC, date=date(2023, 3, 19)),
    EventRecord(chapter=ARC, date=date(2023, 5, 14)),
    EventRecord(chapter=ARC, date=date(2023, 6, 18)),
    EventRecord(chapter=ARC, date=date(2023, 7, 16)),
    EventRecord(chapter=ARC, date=date(2023, 8, 13)),
    EventRecord(chapter=ARC, date=date(2023, 9, 3)),
    EventRecord(chapter=ARC, date=date(2023, 10, 2), xp_value=12),
    # Some future and hypothetical events.
    EventRecord(chapter=GRM, date=date(2024, 3, 17)),
    # What if Grimoire ran a second April game, after the Arcanorum game?
    EventRecord(chapter=ARC, date=date(2024, 4, 14)),
    EventRecord(chapter=GRM, date=date(2024, 4, 21)),
    EventRecord(chapter=GRM, date=date(2024, 4, 25)),
]


@pytest.fixture
def campaign() -> CampaignRecord:
    campaign = CampaignRecord(name="Tempest Test", start_year=2023)
    return campaign.add_events(EVENT_HISTORY)


def test_compute_max_xp(campaign: CampaignRecord):
    assert campaign.max_xp == 92


def test_compute_max_cp(campaign: CampaignRecord):
    assert campaign.max_cp == 11


def test_compute_max_bonus_cp(campaign: CampaignRecord):
    assert campaign.max_bonus_cp == 6


def test_get_historical_values_on_event_date(campaign: CampaignRecord):
    """If we ask for a date equal to an entry, we get that entry."""
    values = campaign.get_historical_values(date(2024, 3, 17))
    assert values.date == date(2024, 3, 17)


def test_get_historical_values_most_recent(campaign: CampaignRecord):
    """If we ask for an arbitrary date, we get the latest entry before it."""
    values = campaign.get_historical_values(date(2023, 9, 20))
    assert values.date == date(2023, 9, 3)


def test_get_historical_values_in_future(campaign: CampaignRecord):
    """If we ask for a date after all events, we get the last values."""
    values = campaign.get_historical_values(date(2025, 12, 25))
    assert values.date == date(2024, 4, 25)


def test_get_historical_values_in_past(campaign: CampaignRecord):
    """If we ask for a date before the game started, we get zeros."""
    values = campaign.get_historical_values(date(1999, 12, 25))
    assert values.date == date(2023, 1, 1)


def test_last_event_date(campaign: CampaignRecord):
    assert campaign.last_event_date == date(2024, 4, 25)


def test_value_table(campaign: CampaignRecord):
    """Assert the entire contents of the value table."""
    assert len(campaign.value_table) == 11
    # First game of the season was Arcanorum March
    assert campaign.value_table[0] == CampaignValues(
        date=date(2023, 3, 19),
        max_xp=8,
        max_cp=1,
        max_bonus_cp=3,
    )
    # Second game of the season was Arcanorum April.
    # Grimoire April did not move the max values.
    assert campaign.value_table[1] == CampaignValues(
        date=date(2023, 4, 16),
        max_xp=16,
        max_cp=2,
        max_bonus_cp=3,
    )
    # The next Grimoire event is in August, so the entries until
    # then are all Arcanorum.
    assert campaign.value_table[2] == CampaignValues(
        date=date(2023, 5, 14),
        max_xp=24,
        max_cp=3,
        max_bonus_cp=3,
    )
    assert campaign.value_table[3] == CampaignValues(
        date=date(2023, 6, 18),
        max_xp=32,
        max_cp=4,
        max_bonus_cp=3,
    )
    assert campaign.value_table[4] == CampaignValues(
        date=date(2023, 7, 16),
        max_xp=40,
        max_cp=5,
        max_bonus_cp=3,
    )
    # August: Arcanorum, then Grimoire had 2-days.
    assert campaign.value_table[5] == CampaignValues(
        date=date(2023, 8, 13),
        max_xp=48,
        max_cp=6,
        max_bonus_cp=3,
    )
    # September: Same pattern
    assert campaign.value_table[6] == CampaignValues(
        date=date(2023, 9, 3),
        max_xp=56,
        max_cp=7,
        max_bonus_cp=3,
    )
    # October: Arcanorum had a game that started in September but
    # didn't end until October, and it was a 3-day (12 XP instead of 8).
    # Grimoire also had an October game, but later.
    assert campaign.value_table[7] == CampaignValues(
        date=date(2023, 10, 2),
        max_xp=68,
        max_cp=8,
        max_bonus_cp=3,
    )
    # Season 2! Grimoire runs a March event, but Arc doesn't.
    assert campaign.value_table[8] == CampaignValues(
        date=date(2024, 3, 17),
        max_xp=76,
        max_cp=9,
        max_bonus_cp=6,
    )
    # Arc and Grim both run in April, with Arc going first.
    assert campaign.value_table[9] == CampaignValues(
        date=date(2024, 4, 14),
        max_xp=84,
        max_cp=10,
        max_bonus_cp=6,
    )
    # ...and then hypothetically, what if Grimoire ran a second April event?
    assert campaign.value_table[10] == CampaignValues(
        date=date(2024, 4, 25),
        max_xp=92,
        max_cp=11,
        max_bonus_cp=6,
    )


def test_incremental_updates(campaign: CampaignRecord):
    """If we build a campaign up event-by-event, do we get the same result?"""
    inc_campaign = CampaignRecord(name=campaign.name, start_year=campaign.start_year)

    # When doing incremental updates, we need to be sure we do them in actual order, so sort first.
    events = sorted(EVENT_HISTORY, key=DATE_KEY)
    for event in events:
        inc_campaign = inc_campaign.add_events([event])
        assert inc_campaign.last_event_date == event.date
    assert inc_campaign == campaign


def test_add_old_events(campaign: CampaignRecord):
    """Adding old events to an existing campaign should result in a no-op if already added."""

    updated_campaign = campaign.add_events(EVENT_HISTORY)
    assert updated_campaign == campaign


def test_add_ahistorical_events(campaign: CampaignRecord):
    """Adding events to the past that could affect the future doesn't affect the future."""

    # An extra Arcanorum March game would unbalance the space-time continuum!
    updated_campaign = campaign.add_events(
        [
            EventRecord(
                chapter=ARC,
                date=date(2023, 3, 31),
                xp_value=8,
            )
        ]
    )

    assert updated_campaign == campaign
