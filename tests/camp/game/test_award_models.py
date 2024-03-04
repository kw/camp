from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from allauth.account.models import EmailAddress

from camp.accounts.models import User
from camp.character.models import Character
from camp.engine.rules.tempest.records import AwardRecord
from camp.game.models import Award
from camp.game.models import Campaign
from camp.game.models import Game
from camp.game.models.game_models import PlayerCampaignData


@pytest.fixture
def game():
    return Game.objects.create(
        name="Test Game",
        is_open=True,
    )


@pytest.mark.django_db
@pytest.fixture
def campaign(game):
    return Campaign.objects.create(
        name="Test Campaign",
        start_year=2020,
        game=game,
        is_open=True,
    )


@pytest.mark.django_db
def test_closed_campaign(campaign):
    """Only awards for open campaigns are displayed."""
    campaign.is_open = False
    campaign.save()

    bob = User.objects.create(username="bob")

    # Regardless of whether the awards are tied to a
    # verified email, an unverified email, or directly to
    # a player account, they won't be returned.
    Award.objects.create(
        campaign=campaign,
        email="Bob@GMail.com",
        award_data={},
    )

    Award.objects.create(
        campaign=campaign,
        email="robert@gmail.com",
        award_data={},
    )

    Award.objects.create(
        campaign=campaign,
        player=bob,
        award_data={},
    )

    claimable, unclaimable = Award.unclaimed_for(bob)
    assert claimable.count() == 0
    assert unclaimable.count() == 0


@pytest.mark.django_db
def test_unclaimed_awards(campaign):
    """We can retrieve awards that could be claimed for a player."""
    bob = User.objects.create(username="bob")
    other = User.objects.create(username="other")

    EmailAddress.objects.create(
        user=bob,
        email="bob@gmail.com",
        verified=True,
    )
    EmailAddress.objects.create(
        user=bob,
        email="robert@gmail.com",
        verified=False,
    )

    # These awards have slight variations on Bob's email,
    # and will be included as claimable.
    award1 = Award.objects.create(
        campaign=campaign,
        email="Bob@GMail.com",
        award_data={},
    )

    award2 = Award.objects.create(
        campaign=campaign,
        email="bob@gmail.com",
        award_data={},
    )

    # Bob previously used another account with the same
    # email address and claimed an award there. This award
    # won't appear in the unclaimed list.
    Award.objects.create(
        campaign=campaign,
        email="bob@gmail.com",
        award_data={},
        player=other,
    )

    # This award isn't associated with Bob in any way, and won't be included.
    Award.objects.create(
        campaign=campaign,
        email="larry@gmail.com",
        award_data={},
    )

    # Award targeting one of Bob's alternate addresses. It hasn't been verified,
    # so it will be in the list but not marked as claimable.
    award5 = Award.objects.create(
        campaign=campaign,
        email="robert@gmail.com",
        award_data={},
    )

    # Award where Bob is the assigned player, but it hasn't
    # been claimed yet.
    award6 = Award.objects.create(
        campaign=campaign,
        player=bob,
        award_data={},
    )

    # Award assigned to Bob that has already been claimed.
    Award.objects.create(
        campaign=campaign,
        player=bob,
        award_data={},
        applied_date=datetime(2020, 1, 1, tzinfo=UTC),
    )

    # Award assigned to another player that should be
    # claimable, but not by Bob.
    Award.objects.create(
        campaign=campaign,
        player=other,
        award_data={},
    )

    should_be_claimable = {award1.id, award2.id, award6.id}
    should_be_unclaimable = {award5.id}

    # Finally, actually test it.

    claimable, unclaimable = Award.unclaimed_for(bob)

    claimable_ids = {a.id for a in claimable}
    unclaimable_ids = {a.id for a in unclaimable}

    assert claimable_ids == should_be_claimable
    assert unclaimable_ids == should_be_unclaimable


@pytest.mark.django_db
def test_claim_award(game, campaign):
    """In the happy path, claiming works as expected for email awards."""
    bob = User.objects.create(username="bob")
    EmailAddress.objects.create(
        user=bob,
        email="bob@gmail.com",
        verified=True,
    )

    award = Award.objects.create(
        campaign=campaign,
        email="Bob@GMail.com",
        award_data=AwardRecord(date=date(2020, 2, 2), bonus_cp=1).model_dump(
            mode="json"
        ),
    )

    character = Character.objects.create(
        owner=bob,
        game=game,
        campaign=campaign,
    )

    assert award.needs_character

    award.claim(bob, character)

    assert award.applied_date is not None
    assert award.check_applied()

    record = PlayerCampaignData.retrieve_model(bob, campaign).record
    assert record.characters[character.id].bonus_cp == 1


@pytest.mark.django_db
def test_claim_assigned_award(game, campaign):
    """In the happy path, claiming works as expected for assigned awards."""
    bob = User.objects.create(username="bob")

    award = Award.objects.create(
        campaign=campaign,
        player=bob,
        award_data=AwardRecord(date=date(2020, 2, 2), bonus_cp=1).model_dump(
            mode="json"
        ),
    )

    character = Character.objects.create(
        owner=bob,
        game=game,
        campaign=campaign,
    )

    assert award.needs_character

    award.claim(bob, character)

    assert award.applied_date is not None
    assert award.check_applied()

    record = PlayerCampaignData.retrieve_model(bob, campaign).record
    assert record.characters[character.id].bonus_cp == 1


@pytest.mark.django_db
def test_claim_award_unverified(game, campaign):
    """An unverified address isn't good enough to claim."""
    bob = User.objects.create(username="bob")
    EmailAddress.objects.create(
        user=bob,
        email="bob@gmail.com",
        verified=False,
    )

    award = Award.objects.create(
        campaign=campaign,
        email="Bob@GMail.com",
        award_data=AwardRecord(date=date(2020, 2, 2), bonus_cp=1).model_dump(
            mode="json"
        ),
    )

    character = Character.objects.create(
        owner=bob,
        game=game,
        campaign=campaign,
    )

    with pytest.raises(ValueError):
        award.claim(bob, character)

    assert award.applied_date is None
    assert not award.check_applied()


@pytest.mark.django_db
def test_claim_award_freeplay(game, campaign):
    """Can't claim a character in the wrong/none campaign."""
    bob = User.objects.create(username="bob")
    EmailAddress.objects.create(
        user=bob,
        email="bob@gmail.com",
        verified=True,
    )

    award = Award.objects.create(
        campaign=campaign,
        email="Bob@GMail.com",
        award_data=AwardRecord(date=date(2020, 2, 2), bonus_cp=1).model_dump(
            mode="json"
        ),
    )

    character = Character.objects.create(
        owner=bob,
        game=game,
        campaign=None,
    )

    with pytest.raises(ValueError):
        award.claim(bob, character)

    assert award.applied_date is None
    assert not award.check_applied()


@pytest.mark.django_db
def test_claim_award_other_character(game, campaign):
    """Can't claim an award with someone else's character."""
    bob = User.objects.create(username="bob")
    other = User.objects.create(username="other")

    EmailAddress.objects.create(
        user=bob,
        email="bob@gmail.com",
        verified=True,
    )

    award = Award.objects.create(
        campaign=campaign,
        email="Bob@GMail.com",
        award_data=AwardRecord(date=date(2020, 2, 2), bonus_cp=1).model_dump(
            mode="json"
        ),
    )

    character = Character.objects.create(
        owner=other,
        game=game,
        campaign=campaign,
    )

    with pytest.raises(ValueError):
        award.claim(bob, character)

    assert award.applied_date is None
    assert not award.check_applied()


@pytest.mark.django_db
def test_claim_assigned_to_other_player(game, campaign):
    """Can't claim an award assigned to someone else."""
    bob = User.objects.create(username="bob")
    other = User.objects.create(username="other")

    award = Award.objects.create(
        campaign=campaign,
        player=other,
        award_data=AwardRecord(date=date(2020, 2, 2), bonus_cp=1).model_dump(
            mode="json"
        ),
    )

    character = Character.objects.create(
        owner=bob,
        game=game,
        campaign=campaign,
    )

    assert award.needs_character

    with pytest.raises(ValueError):
        award.claim(bob, character)

    assert award.applied_date is None
    assert not award.check_applied()
