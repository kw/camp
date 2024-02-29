import pytest
from allauth.account.models import EmailAddress

from camp.accounts.models import User
from camp.game.models import Award
from camp.game.models import Campaign
from camp.game.models import Game


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
    )


@pytest.mark.django_db
def test_unclaimed_awards(campaign):
    bob = User.objects.create(username="bob")
    other = User.objects.create(username="other")

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

    should_be_claimable = {award1.id, award2.id}
    should_be_unclaimable = {award5.id}

    # Finally, actually test it.

    claimable, unclaimable = list(Award.unclaimed_for(bob))

    claimable_ids = {a.id for a in claimable}
    unclaimable_ids = {a.id for a in unclaimable}

    assert claimable_ids == should_be_claimable
    assert unclaimable_ids == should_be_unclaimable
