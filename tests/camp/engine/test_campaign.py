from __future__ import annotations

from datetime import date

import pytest

from camp.engine.rules.tempest.campaign import Campaign
from camp.engine.rules.tempest.campaign import CampaignValues
from camp.engine.rules.tempest.campaign import Event

GRM = "grimoire"
ARC = "arcanorum"

# Note that the event history isn't presented in any particular order...
EVENT_HISTORY = [
    Event(chapter=GRM, start_date=date(2023, 4, 28), end_date=date(2023, 4, 30)),
    Event(chapter=GRM, start_date=date(2023, 8, 25), end_date=date(2023, 8, 27)),
    Event(chapter=GRM, start_date=date(2023, 9, 22), end_date=date(2023, 9, 24)),
    Event(chapter=GRM, start_date=date(2023, 10, 27), end_date=date(2023, 10, 29)),
    Event(chapter=ARC, start_date=date(2023, 4, 14), end_date=date(2023, 4, 16)),
    Event(chapter=ARC, start_date=date(2023, 3, 17), end_date=date(2023, 3, 19)),
    Event(chapter=ARC, start_date=date(2023, 5, 12), end_date=date(2023, 5, 14)),
    Event(chapter=ARC, start_date=date(2023, 6, 16), end_date=date(2023, 6, 18)),
    Event(chapter=ARC, start_date=date(2023, 7, 14), end_date=date(2023, 7, 16)),
    Event(chapter=ARC, start_date=date(2023, 8, 11), end_date=date(2023, 8, 13)),
    Event(chapter=ARC, start_date=date(2023, 9, 1), end_date=date(2023, 9, 3)),
    Event(chapter=ARC, start_date=date(2023, 9, 29), end_date=date(2023, 10, 2)),
]


@pytest.fixture
def campaign() -> Campaign:
    campaign = Campaign(name="Tempest Test")
    campaign.add_events(EVENT_HISTORY)
    return campaign


def test_compute_max_xp(campaign: Campaign):
    assert campaign.max_xp == 60


def test_compute_max_cp(campaign: Campaign):
    assert campaign.max_cp == 8


def test_compute_max_bonus_cp(campaign: Campaign):
    assert campaign.max_bonus_cp == 3


def test_get_historical_values(campaign: Campaign):
    values = campaign.get_historical_values(date(2023, 9, 20))
    assert values == CampaignValues(
        effective_date=date(2023, 8, 30),
        max_xp=52,
        max_cp=7,
        max_bonus_cp=3,
    )
