from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal

import pytest
import time_machine

import camp.game.models
from camp.character import models


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="testuser",
    )


@pytest.fixture
def game():
    game = camp.game.models.Game.objects.first()
    ruleset = game.rulesets.create(package="camp.tempest.v1")
    assert ruleset.ruleset.bad_defs == []
    return game


@pytest.fixture
def campaign(game):
    return camp.game.models.Campaign.objects.create(
        name="Test",
        slug="test",
        game=game,
        start_year=2023,
    )


@pytest.fixture
def chapter(game):
    return camp.game.models.Chapter.objects.create(
        name="Test Chapter",
        slug="testchapter",
        game=game,
    )


@pytest.fixture
def character(game, campaign, user):
    return models.Character.objects.create(
        name="Test",
        game=game,
        campaign=campaign,
        owner=user,
    )


@pytest.fixture
def first_event(campaign, chapter):
    return camp.game.models.Event.objects.create(
        campaign=campaign,
        chapter=chapter,
        registration_open=datetime(2023, 1, 1, tzinfo=UTC),
        event_start_date=datetime(2023, 1, 10, 12, tzinfo=UTC),
        event_end_date=datetime(2023, 1, 14, 12, tzinfo=UTC),
        # Make this a longer event so that it causes a level-up.
        logistics_periods=Decimal(6),
    )


@pytest.fixture
def user_client(client, user):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_character_lifecycle(user, user_client, character, first_event):
    """Integration test for creating a character, playing them at an event, and updating them later."""
    # TODO: Once we support creating campaign characters in the web UI,
    # move this into the test flow. For now, we use a fixture.

    # response = user_client.post("/characters/new/", {"name": "test"})
    # assert response.status_code == 302
    # assert response.url == "/characters/1/"
    id = character.id

    # Purchase 2 levels of Mage
    response = user_client.post(
        f"/characters/{id}/f/mage/", {"purchase": True, "ranks": 2}
    )
    assert response.status_code == 302
    assert response.url == f"/characters/{id}/f/mage/"

    # Register for the event.
    with time_machine.travel(date(2023, 1, 2)):
        response = user_client.post(
            f"/events/{first_event.id}/register/",
            {
                "profile-legal_name": "Legally Bob",
                "profile-birthdate": "1999-01-01",
                "reg-is_npc": "False",
                "reg-attendance": "0",
                "reg-lodging": "0",
                "reg-character": str(character.id),
            },
        )
        assert response.status_code == 302
        assert response.url == f"/events/{first_event.id}/"

    # Behind the scenes, complete the event and mark attendance.
    with time_machine.travel(date(2023, 1, 14)):
        first_event.mark_complete()
        reg = first_event.registrations.first()
        # This isn't really a logistics user, but let's not bother creating one...
        reg.apply_award(user)

    # We should now be able to add a new level.
    response = user_client.post(
        f"/characters/{id}/f/mage/", {"purchase": True, "ranks": 3}
    )
    assert response.status_code == 302
    assert response.url == f"/characters/{id}/f/mage/"

    # Read the character out of the database and check if they have the spells
    character = models.Character.objects.get(pk=1)
    controller = character.primary_sheet.controller
    assert controller.get("mage") == 3
