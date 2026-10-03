from __future__ import annotations

from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_buy_role(character: TempestCharacter):
    character.freeplay_cp = 1
    assert character.can_purchase("shopkeeper")
    assert character.apply("shopkeeper")
    assert character.cp.spent_cp == 2

    role = character.feature_controller("shopkeeper")
    assert not role.level_label()


def test_get_innate(character: TempestCharacter):
    character.freeplay_cp = 1
    assert character.get("shop-income") == 0
    character.apply("shopkeeper")

    assert character.get("shop-income") == 1


def test_cant_buy_role_power_without_role(character: TempestCharacter):
    character.freeplay_cp = 10
    assert not character.can_purchase("restock")
    assert not character.apply("restock")


def test_can_buy_role_power_with_role(character: TempestCharacter):
    character.freeplay_cp = 10
    character.apply("shopkeeper")
    assert character.can_purchase("restock")
    assert character.apply("restock")

    role = character.feature_controller("shopkeeper")
    assert role.level_label() == "Basic"


def test_cant_buy_advanced_power_without_all_basics(character: TempestCharacter):
    character.freeplay_cp = 10
    character.apply("shopkeeper")
    character.apply("restock")  # One Basic power, but not both.
    assert not character.can_purchase("banhammer")
    assert not character.apply("banhammer")


def test_can_buy_advanced_power_with_all_basics(character: TempestCharacter):
    character.freeplay_cp = 10
    character.apply("shopkeeper")
    character.apply("restock")
    character.apply("shop-appraisal")

    assert character.can_purchase("banhammer")
    assert character.apply("banhammer")

    role = character.feature_controller("shopkeeper")
    assert role.level_label() == "Advanced"


def test_buy_all_powers(character: TempestCharacter):
    character.freeplay_cp = 20
    character.apply("shopkeeper")
    character.apply("restock")
    character.apply("shop-appraisal")
    character.apply("banhammer")
    character.apply("detect-thief")

    role = character.feature_controller("shopkeeper")
    assert role.level_label() == "MAX"


def test_buy_bonus_power(character: TempestCharacter):
    character.freeplay_cp = 10

    assert not character.can_purchase("cashbox")
    character.apply("shopkeeper")
    assert character.can_purchase("cashbox")
    assert character.apply("cashbox")
