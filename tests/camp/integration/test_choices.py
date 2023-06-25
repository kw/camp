from typing import cast

import pytest

import camp.game.models
from camp.character import models
from camp.engine.rules.tempest.controllers.feature_controller import FeatureController


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="testuser",
    )


@pytest.fixture
def user_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        game = camp.game.models.Game.objects.first()
        ruleset = game.rulesets.create(package="camp.tempest.v1")
        assert ruleset.ruleset.bad_defs == []


@pytest.mark.django_db
def test_choices(user_client):
    """Integration test for kw/camp#61.

    See tempest_v1/test_granted_choices.py for a unit test of the same issue.
    """
    response = user_client.post("/characters/new/", {"name": "test"})
    assert response.status_code == 302
    assert response.url == "/characters/1/"

    # Purchase 2 levels of Mage
    response = user_client.post("/characters/1/f/mage/", {"purchase": True, "ranks": 2})
    assert response.status_code == 302
    assert response.url == "/characters/1/f/mage/"

    # Choose a spell for Novice Spell-scholar
    response = user_client.post(
        "/characters/1/f/novice-spell-scholar/",
        {"choice": "spell", "selection": "bolster-shield"},
    )
    assert response.status_code == 302
    assert response.url == "/characters/1/f/novice-spell-scholar/"

    # Choose a second spell for Novice Spell-scholar
    response = user_client.post(
        "/characters/1/f/novice-spell-scholar/",
        {"choice": "spell", "selection": "carnate"},
    )
    assert response.status_code == 302
    assert response.url == "/characters/1/f/novice-spell-scholar/"

    # Read the character out of the database and check if they have the spells
    character = models.Character.objects.get(pk=1)
    controller = character.primary_sheet.controller
    assert controller.get("mage") == 2

    spellscholar = cast(
        FeatureController, controller.controller("novice-spell-scholar")
    )
    assert spellscholar.value > 0
    spell_choice = spellscholar.choices["spell"]
    assert spell_choice
    assert spell_choice.taken_choices().keys() == {"bolster-shield", "carnate"}

    assert controller.get("bolster-shield")
    assert controller.get("carnate")
