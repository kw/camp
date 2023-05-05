from __future__ import annotations

from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_basic_flaw(character: TempestCharacter):
    assert character.can_purchase("basic-flaw")
    assert character.apply("basic-flaw")
    assert character.cp.flaw_award_cp == 1
    # can't buy it more than once
    assert not character.can_purchase("basic-flaw")


def test_exceed_flaw_cap(character: TempestCharacter):
    assert character.apply("basic-flaw")
    # Even though this would put us over flaw cap, we can still buy it
    assert character.can_purchase("big-flaw")
    assert character.apply("big-flaw")
    # ...but that doesn't put us over flaw cap
    assert character.cp.flaw_award_cp == 5


def test_conflicting_requirements(character: TempestCharacter):
    # If flaws have conflicting requirements, they can't both
    # be purchased.
    assert character.apply("conflicting-mod-a")
    assert not character.can_purchase("conflicting-mod-b")
    assert not character.apply("conflicting-mod-b")


def test_option_award_1(character: TempestCharacter):
    rd = character.can_purchase("option-award-flaw")
    assert rd.needs_option

    assert character.can_purchase("option-award-flaw+Something")
    assert character.apply("option-award-flaw+Something")
    assert character.cp.flaw_award_cp == 1


def test_option_award_2(character: TempestCharacter):
    rd = character.can_purchase("option-award-flaw")
    assert rd.needs_option

    assert character.can_purchase("option-award-flaw+Something_Else")
    assert character.apply("option-award-flaw+Something_Else")
    assert character.cp.flaw_award_cp == 2


def test_option_flag_1(character: TempestCharacter):
    rd = character.can_purchase("option-flag-flaw")
    assert rd.needs_option

    assert character.can_purchase("option-flag-flaw+Foo")
    assert character.apply("option-flag-flaw+Foo")
    assert character.cp.flaw_award_cp == 1


def test_option_flag_2(character: TempestCharacter):
    rd = character.can_purchase("option-flag-flaw")
    assert rd.needs_option

    assert character.can_purchase("option-flag-flaw+Xyzzy")
    assert character.apply("option-flag-flaw+Xyzzy")
    assert character.cp.flaw_award_cp == 2


def test_award_mod(character: TempestCharacter):
    # This flaw is worth 2, unless the character has basic-flaw,
    # in which case it's worth 1.
    assert character.apply("award-mod-flaw")
    assert character.cp.flaw_award_cp == 2

    assert character.apply("basic-flaw")
    assert character.cp.flaw_award_cp == 2


def test_overcome_flaw(character: TempestCharacter):
    character.apply("basic-flaw")
    assert character.get_prop("basic-flaw") == 1
    assert character.cp.flaw_overcome_cp == 0

    character.flaws["basic-flaw"].overcome = True
    assert character.cp.flaw_award_cp == 1
    assert character.cp.flaw_overcome_cp == 3
    assert character.get_prop("basic-flaw") == 0


def test_suppress_flaw(character: TempestCharacter):
    character.apply("basic-flaw")
    assert character.get_prop("basic-flaw") == 1
    assert character.cp.flaw_overcome_cp == 0

    character.flaws["basic-flaw"].model.plot_suppressed = True
    assert character.cp.flaw_award_cp == 1
    assert character.cp.flaw_overcome_cp == 0
    assert character.get_prop("basic-flaw") == 0


def test_no_cp_awarded(character: TempestCharacter):
    character.apply("basic-flaw")
    assert character.get_prop("basic-flaw") == 1
    assert character.cp.flaw_overcome_cp == 0

    character.flaws["basic-flaw"].model.plot_free = True
    assert character.cp.flaw_award_cp == 0
    assert character.cp.flaw_overcome_cp == 0
    assert character.get_prop("basic-flaw") == 1
