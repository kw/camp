"""Basic tests for the character controller."""
from __future__ import annotations

from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter
from camp.engine.rules.tempest.engine import TempestEngine


def test_serialization_flow(engine: TempestEngine, character: TempestCharacter):
    """A character with data in it can be serialized and deserialized safely."""
    # Apply some mutations
    character.xp_level = 10
    assert character.apply("fighter:5")
    assert character.apply("cleric:5")
    assert character.apply("basic-skill")
    assert character.apply("basic-flaw")
    assert character.apply("basic-perk")
    assert character.apply("specific-options#One")
    assert character.apply("inherited-option#One")
    assert character.meets_requirements("martial:5")
    assert character.meets_requirements("divine:5")

    data = character.dump_dict()
    assert data

    loaded = engine.load_character(data)

    assert (
        character is not loaded
    )  # We didn't just get a reference to the original somehow.
    del character  # Don't accidentally reference the original below

    assert loaded.meets_requirements("martial:5")
    assert loaded.meets_requirements("divine:5")
    assert loaded.meets_requirements("basic-skill")
    assert loaded.meets_requirements("basic-flaw")
    assert loaded.meets_requirements("basic-perk")
    assert loaded.meets_requirements("specific-options#One")
    assert loaded.meets_requirements("inherited-option#One")

    assert data == loaded.dump_dict()
