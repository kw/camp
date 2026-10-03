from __future__ import annotations

from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_buy_breed(character: TempestCharacter):
    assert character.can_purchase("human")
    assert character.apply("human")


def test_add_challenge(character: TempestCharacter):
    assert not character.can_purchase("self-important")

    assert character.apply("human")
    assert character.get("bp-primary") == 0

    assert character.can_purchase("self-important")
    assert character.apply("self-important")

    assert character.get("bp-primary") == 5


def test_buy_advantage(character: TempestCharacter):
    character.apply("human")
    character.apply("self-important")

    assert character.can_purchase("easy-costume")  # Grants 5 BP
    assert character.apply("easy-costume")  # Costs 4 BP

    assert character.get("bp-primary") == 1
