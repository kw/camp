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
