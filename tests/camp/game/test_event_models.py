from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
import time_machine

from camp.game.models import Campaign
from camp.game.models import Chapter
from camp.game.models import Event
from camp.game.models import Game


@pytest.fixture
def game():
    return Game.objects.create(
        name="Test Game",
        is_open=True,
    )


@pytest.fixture
def chapter(game):
    return Chapter.objects.create(
        game=game,
        slug="florida",
        name="Florida",
        timezone="UTC",
    )


@pytest.mark.django_db
@pytest.fixture
def campaign(game):
    return Campaign.objects.create(
        name="Test Campaign",
        start_year=2020,
        game=game,
    )


@pytest.mark.django_db
@pytest.fixture
def event(chapter, campaign):
    return Event.objects.create(
        name="Test Event 1",
        chapter=chapter,
        campaign=campaign,
        event_start_date=datetime(2020, 1, 2, 12, tzinfo=UTC),
        event_end_date=datetime(2020, 1, 5, 12, tzinfo=UTC),
    )


@pytest.mark.django_db
@pytest.fixture
def event2(chapter, campaign):
    return Event.objects.create(
        name="Test Event 2",
        chapter=chapter,
        campaign=campaign,
        event_start_date=datetime(2020, 2, 2, 12, tzinfo=UTC),
        event_end_date=datetime(2020, 2, 5, 12, tzinfo=UTC),
    )


@pytest.mark.django_db
def test_mark_event_complete_during_event(campaign, event):
    """Marking the event complete works after the event starts."""
    # Before we start, this campaign doesn't have any progress.
    campaign_record = campaign.record
    assert not campaign_record.recent_events
    assert campaign_record.max_xp == 0

    with time_machine.travel(date(2020, 1, 3)):
        # But once the event has started, we can mark it.
        can_complete, _ = event.can_complete()
        assert can_complete

        event.mark_complete()

    assert event.completed

    # Now, the campaign has progressed, and there's a recent event.
    campaign.refresh_from_db()
    campaign_record = campaign.record
    assert len(campaign_record.recent_events) == 1
    assert campaign_record.max_xp == 8


@pytest.mark.django_db
def test_mark_event_complete_before_event(event):
    """Before the event, we can't mark it complete."""
    with time_machine.travel(date(2020, 1, 1)):
        can_complete, _ = event.can_complete()
        assert not can_complete

        with pytest.raises(ValueError):
            event.mark_complete()

    assert not event.completed


@pytest.mark.django_db
def test_mark_event_complete_twice(campaign, event):
    """Marking an event completed twice is prevented."""

    with time_machine.travel(date(2020, 1, 3)):
        # But once the event has started, we can mark it.
        can_complete, _ = event.can_complete()
        assert can_complete

        event.mark_complete()
        assert event.completed

        can_still_complete, _ = event.can_complete()
        assert not can_still_complete

        with pytest.raises(ValueError):
            event.mark_complete()

    # The campaign remains properly marked.
    campaign.refresh_from_db()
    campaign_record = campaign.record
    assert len(campaign_record.recent_events) == 1
    assert campaign_record.max_xp == 8


@pytest.mark.django_db
def test_mark_second_event(campaign, event, event2):
    """Marking a second event works."""

    with time_machine.travel(date(2020, 1, 3)):
        event.mark_complete()

    campaign.refresh_from_db()
    assert len(campaign.record.recent_events) == 1

    with time_machine.travel(date(2020, 2, 3)):
        event2.mark_complete()

    # The campaign remains properly marked.
    campaign.refresh_from_db()
    campaign_record = campaign.record
    # Only 1 event in recent_events because each event is in a different month.
    assert len(campaign_record.recent_events) == 1
    assert campaign_record.max_xp == 16


@pytest.mark.django_db
def test_mark_events_out_of_order(campaign, event, event2):
    """Marking an event _prior_ to the last event is prevented."""

    with time_machine.travel(date(2020, 2, 3)):
        event2.mark_complete()
        campaign.refresh_from_db()

        # The second event can't be completed.
        can_complete, _ = event.can_complete()
        assert not can_complete
        with pytest.raises(ValueError):
            event.mark_complete()

    # The campaign remains properly marked.
    campaign.refresh_from_db()
    campaign_record = campaign.record
    assert len(campaign_record.recent_events) == 1
    assert campaign_record.max_xp == 8
