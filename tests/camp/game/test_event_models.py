from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

import pytest
import time_machine

from camp.accounts.models import User
from camp.character.models import Character
from camp.engine.rules.tempest.records import AwardCategory
from camp.engine.rules.tempest.records import AwardRecord
from camp.engine.rules.tempest.records import CharacterRecord
from camp.game.models import Campaign
from camp.game.models import Chapter
from camp.game.models import Event
from camp.game.models import Game
from camp.game.models.event_models import EventRegistration
from camp.game.models.event_models import Lodging
from camp.game.models.game_models import PlayerCampaignData


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


@pytest.mark.django_db
def test_apply_award(campaign, game, event):
    """A player registered for an event that completes; marking their attendance works."""
    user = User.objects.create(username="testuser")
    logi = User.objects.create(username="logistics")

    character = Character.objects.create(
        name="Bob",
        game=game,
        campaign=campaign,
        owner=user,
    )
    registration = EventRegistration.objects.create(
        event=event,
        user=user,
        character=character,
        lodging=Lodging.NONE,
    )

    apply_time = event.event_end_date + timedelta(hours=1)

    with time_machine.travel(apply_time, tick=False):
        event.mark_complete()
        registration.apply_award(applied_by=logi)

    player_data = PlayerCampaignData.objects.get(user=user, campaign=campaign)
    record = player_data.record

    assert registration.award_applied_by == logi
    assert registration.award_applied_date == apply_time
    assert registration.attended

    assert record.user == user.id
    assert record.events_played == 1
    assert record.last_played == event.event_end_date.date()
    assert record.last_campaign_date == event.event_end_date.date()
    assert record.xp == 8
    assert record.awards == [
        AwardRecord(
            date=event.event_end_date.date(),
            source_id=event.id,
            category=AwardCategory.EVENT,
            description="PC Event Credit for Test Event 1",
            event_played=True,
            character=character.id,
            event_xp=8,
            event_cp=1,
        )
    ]
    assert record.characters == {
        character.id: CharacterRecord(
            id=character.id,
            event_cp=1,
            events_played=1,
            last_played=event.event_end_date.date(),
        )
    }


@pytest.mark.django_db
def test_apply_award_not_complete(campaign, game, event):
    """Marking attendance won't work until the event is marked complete."""
    user = User.objects.create(username="testuser")
    logi = User.objects.create(username="logistics")

    character = Character.objects.create(
        name="Bob",
        game=game,
        campaign=campaign,
        owner=user,
    )
    registration = EventRegistration.objects.create(
        event=event,
        user=user,
        character=character,
        lodging=Lodging.NONE,
    )

    apply_time = event.event_end_date + timedelta(hours=1)

    with time_machine.travel(apply_time, tick=False):
        # Event NOT marked complete
        with pytest.raises(ValueError):
            registration.apply_award(applied_by=logi)


@pytest.mark.django_db
def test_apply_award_canceled_registration(campaign, game, event):
    """Marking attendance for a canceled registration fails."""
    user = User.objects.create(username="testuser")
    logi = User.objects.create(username="logistics")

    character = Character.objects.create(
        name="Bob",
        game=game,
        campaign=campaign,
        owner=user,
    )
    registration = EventRegistration.objects.create(
        event=event,
        user=user,
        character=character,
        lodging=Lodging.NONE,
        canceled_date=event.event_start_date - timedelta(days=1),
    )

    apply_time = event.event_end_date + timedelta(hours=1)

    with time_machine.travel(apply_time, tick=False):
        event.mark_complete()
        with pytest.raises(ValueError):
            registration.apply_award(applied_by=logi)


@pytest.mark.django_db
def test_apply_award_twice(campaign, game, event):
    """Marking attendance twice doesn't work."""
    user = User.objects.create(username="testuser")
    logi = User.objects.create(username="logistics")

    character = Character.objects.create(
        name="Bob",
        game=game,
        campaign=campaign,
        owner=user,
    )
    registration = EventRegistration.objects.create(
        event=event,
        user=user,
        character=character,
        lodging=Lodging.NONE,
    )

    apply_time = event.event_end_date + timedelta(hours=1)

    with time_machine.travel(apply_time, tick=False):
        event.mark_complete()
        registration.apply_award(applied_by=logi)  # Works the first time
        with pytest.raises(ValueError):
            registration.apply_award(applied_by=logi)
