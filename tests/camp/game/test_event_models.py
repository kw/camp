from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
import time_machine

from camp.game.models import Campaign
from camp.game.models import Chapter
from camp.game.models import Event
from camp.game.models import Game


@pytest.mark.django_db
def test_mark_event_complete():

    game = Game.objects.create(
        name="Test Game",
        is_open=True,
    )

    campaign = Campaign.objects.create(
        name="Test Campaign",
        start_year=2020,
        game=game,
    )

    chapter = Chapter.objects.create(
        game=game,
        slug="florida",
        name="Florida",
        timezone="UTC",
    )

    event = Event.objects.create(
        name="Test Event 1",
        chapter=chapter,
        campaign=campaign,
        event_start_date=datetime(2020, 1, 2, 12, tzinfo=UTC),
        event_end_date=datetime(2020, 1, 5, 12, tzinfo=UTC),
    )

    # Before we start, this campaign doesn't have any progress.
    campaign_record = campaign.engine_model
    assert not campaign_record.recent_events
    assert campaign_record.max_xp == 0

    with time_machine.travel(date(2020, 1, 1)):
        # Before the event, we can't complete.
        can_complete, _ = event.can_complete()
        assert not can_complete

        with pytest.raises(ValueError):
            event.mark_complete()

    with time_machine.travel(date(2020, 1, 3)):
        # But once the event has started, we can mark it.
        can_complete, _ = event.can_complete()
        assert can_complete

        event.mark_complete()

    assert event.completed

    # Now, the campaign has progressed, and there's a recent event.
    campaign.refresh_from_db()
    campaign_record = campaign.engine_model
    assert len(campaign_record.recent_events) == 1
    assert campaign_record.max_xp == 8
