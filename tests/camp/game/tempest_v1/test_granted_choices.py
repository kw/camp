from camp.engine.rules.base_models import ChoiceMutation
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_mage_spellscholar(character: TempestCharacter):
    """The specific case for kw/camp#61.

    In this case, the character purchases Mage 2, then attempts to choose
    two spells for Novice Spell-scholar. While the system records the success,
    the model for Novice Spell-scholar was not linked to the character model
    since it was not purchased at any point. In previous manual tests, the
    feature had been purchased by the user at some point, causing its model
    to exist in the persisted data. This test ensures that the feature model is
    properly linked to the character model.

    See also integration/test_choices.py for an integration test of the same issue.
    """
    assert character.apply("mage:2")
    assert character.apply(
        ChoiceMutation(
            id="novice-spell-scholar", choice="spell", value="bolster-shield"
        )
    )
    data = character.dump_dict()
    assert "novice-spell-scholar" in data["features"]
    assert (
        "bolster-shield" in data["features"]["novice-spell-scholar"]["choices"]["spell"]
    )


def test_extended_capacity(character: TempestCharacter):
    """Check that Extended Capacity skills allow a sphere to be selected multiple times."""
    assert character.apply("mage:2")
    character.awarded_cp = 10
    slots = character.get("arcane.spell_slots@1")
    # Buy 3 ranks of Extended Capacity.
    assert character.apply("extended-capacity-novice:3")

    # Check that we can choose Arcane.
    controller = character.feature_controller("extended-capacity-novice")
    assert controller.choices["sphere"].available_choices().keys() == {"arcane"}
    assert character.apply(
        ChoiceMutation(id="extended-capacity-novice", choice="sphere", value="arcane")
    )
    assert character.get("arcane.spell_slots@1") == slots + 1

    # Choose Arcane again, we get another slot.
    assert character.apply(
        ChoiceMutation(id="extended-capacity-novice", choice="sphere", value="arcane")
    )
    assert character.get("arcane.spell_slots@1") == slots + 2

    # What if we dip into Divine?

    character.apply("basic-faith")
    controller = character.feature_controller("extended-capacity-novice")
    assert controller.choices["sphere"].available_choices().keys() == {
        "arcane",
        "divine",
    }

    # Choose Divine. We get a slot.
    character.apply(
        ChoiceMutation(id="extended-capacity-novice", choice="sphere", value="divine")
    )
    assert character.get("divine.spell_slots@1") == 1

    # We should be out of choices now, so there should be none available.
    assert controller.choices["sphere"].available_choices().keys() == set()
