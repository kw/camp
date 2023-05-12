from __future__ import annotations

import pytest

from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


@pytest.mark.skip
def test_creation_only_perks(character: TempestCharacter):
    # TODO: Implement this test when we implement the charater creation flag.
    pass


def test_basic_perk(character: TempestCharacter):
    assert character.can_purchase("basic-perk")
    assert character.apply("basic-perk")
    assert character.cp.spent_cp == 1


def test_advanced_perk(character: TempestCharacter):
    """Perks with requirements work as expected."""
    assert not character.can_purchase("advanced-perk")
    character.apply("basic-perk")
    assert character.can_purchase("advanced-perk")
    assert character.apply("advanced-perk")
    assert character.cp.spent_cp == 3


def test_grants_bonus_lp(character: TempestCharacter):
    """Some perks grant bonus life points."""
    starting_lp = character.lp.value
    assert character.apply("grants-bonus-lp-perk")
    assert character.lp.value == starting_lp + 3
    # Stable if we call reconcile?
    character.reconcile()
    assert character.lp.value == starting_lp + 3


def test_skill_discount(character: TempestCharacter):
    character.apply("skill-discount-perk")

    base_cp = character.cp.spent_cp
    assert character.apply("basic-skill")
    # basic-skill only costs 1, so the discount doesn't help.
    assert character.cp.spent_cp == base_cp + 1

    # But one-requirement costs 2, so this'll be cheaper
    assert character.apply("one-requirement")
    assert character.cp.spent_cp == base_cp + 2


def test_perk_discount(character: TempestCharacter):
    character.apply("perk-discount-perk")

    base_cp = character.cp.spent_cp
    assert character.apply("basic-perk")
    # basic-perk only costs 1, so the discount doesn't help
    assert character.cp.spent_cp == base_cp + 1

    # But advanced-perk costs 2, so this'll be cheaper
    assert character.apply("advanced-perk")
    assert character.cp.spent_cp == base_cp + 2


# Patron-related. This also covers some general functionality for Choices.


def test_patron_has_discount_choices(character: TempestCharacter):
    """Perks with choices provide views for those choices once purchased.

    Before a feature is taken, it does not advertise its choices.
    """
    assert not character.feature_controller("patron").choices
    character.apply("patron")
    assert "discount" in character.feature_controller("patron").choices


def test_patron_choice_contains_perks(character: TempestCharacter):
    character.apply("patron")
    discount = character.feature_controller("patron").choices["discount"]
    choices = discount.valid_choices()
    assert "basic-perk" in choices
    assert "basic-skill" not in choices


def test_patron_choice_does_not_contain_tagged(character: TempestCharacter):
    """Perks tagged `no-patron` aren't available for Patron discount."""
    character.apply("patron")
    discount = character.feature_controller("patron").choices["discount"]
    choices = discount.valid_choices()
    # The following perks are tagged "no-patron" in the test ruleset.
    assert "patron" not in choices
    assert "perk-discount-perk" not in choices


def test_patron_discount_applied(character: TempestCharacter):
    character.awarded_cp = 9
    character.apply("patron")
    assert character.cp.spent_cp == 4
    character.apply("varying-cost-perk")
    assert character.cp.spent_cp == 4 + 1
    assert character.apply("varying-cost-perk:4")
    assert character.cp.spent_cp == 4 + sum([1, 1, 2, 2, 3])
    discount = character.feature_controller("patron").choices["discount"]
    assert discount.choose("varying-cost-perk")
    # Discount is applied to each rank individually, and the cost of any
    # given rank can't go below 1.
    assert character.cp.spent_cp == 4 + sum([1, 1, 1, 1, 2])
