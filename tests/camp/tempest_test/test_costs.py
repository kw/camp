from __future__ import annotations

from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_basic_cp_math(character: TempestCharacter):
    # Starting CP is 1 + 2*Level
    assert character.cp.value == 5
    # If we add some CP...
    character.awarded_cp = 5
    assert character.cp.value == 10
    # If we spend CP (basic-skill costs 1 CP)
    character.apply("basic-skill")
    assert character.cp.value == 9
    # Purchase more ranks...
    assert character.apply("basic-skill:9")
    assert character.cp.value == 0
    # Can't purchase any more due to CP cost
    assert not character.can_purchase("basic-skill")


def test_basic_refund(character: TempestCharacter):
    character.awarded_cp = 10
    cp = character.cp.value
    assert character.apply("discounted-skill:5")
    assert character.cp.value == cp - 15

    # Refund all ranks
    assert character.apply("grant-a:5")
    assert character.cp.value == cp

    # Refund more ranks!
    assert character.apply("grant-a:5")
    assert character.cp.value == cp + 15


def test_discounted_skill(character: TempestCharacter):
    """Basic discount semantics.

    'discounted-skill' has a total of 5 ranks, each costing 3 CP.
    """
    character.awarded_cp = 10
    cp = character.cp.value
    assert character.apply("discounted-skill:5")
    assert character.cp.value == cp - 15

    # Apply a 1 CP discount.
    assert character.apply("discount-a")
    assert character.cp.value == cp - 10

    # Apply a 2 CP discount. The skill costs at least 1 CP per rank,
    # even though we now have more discounts than base CP cost.
    assert character.apply("discount-b")
    assert character.cp.value == cp - 5


def test_discount_with_grants(character: TempestCharacter):
    """If a skill with grants have discounts applied, the grants provide an extra discount."""
    character.awarded_cp = 10
    cp = character.cp.value
    assert character.apply("discounted-skill:5")
    assert character.cp.value == cp - 15

    # Apply a 1 CP discount.
    assert character.apply("discount-a")
    assert character.cp.value == cp - 10

    # Get 1 ranks worth of grants. This should refund
    # 3 CP - the discounted cost of 1 rank (2) and the rebate (1).
    assert character.apply("grant-a:1")
    assert character.cp.value == cp - 7

    # Apply a few more.
    assert character.apply("grant-a:2")
    assert character.cp.value == cp - 1

    # What if we grant _all_ the ranks? Not only will the skill be free, but
    # the discount should rebate us some extra CP.
    assert character.apply("grant-a:2")
    assert character.cp.value == cp + 5

    # What if we grant _even more_ ranks? We'll get a refund.
    assert character.apply("grant-a:2")
    assert character.cp.value == cp + 11
