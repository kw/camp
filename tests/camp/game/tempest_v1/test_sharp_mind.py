from camp.engine.rules.base_models import ChoiceMutation
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_lore_discount(character: TempestCharacter):
    """Lore discounts are applied as expected."""
    assert character.apply("artisan:2")
    assert character.apply("sharp-mind")
    assert character.cp.value == 2
    assert character.apply("lore+Arcane")
    assert character.cp.value == 1


def test_lore_available_at_1_cp(character: TempestCharacter):
    """Lore appears in the Skills Available list at 1 CP."""
    assert character.apply("artisan:2")
    assert character.apply("sharp-mind")
    assert character.apply("lore+Arcane")
    features = character.list_features(type="skill", taken=False, available=True)
    feature_ids = [f.full_id for f in features]
    assert "lore" in feature_ids


def test_lore_purchase_at_1_cp(character: TempestCharacter):
    """Purchasing a new Lore works at 1 CP."""
    assert character.apply("artisan:2")
    assert character.apply("sharp-mind")
    assert character.apply("lore+Arcane")
    assert character.apply("lore+Religious")
    assert character.cp.value == 0


def test_lore_available_with_granted(character: TempestCharacter):
    """Lore appears in the Skills Available list at 1 CP...

    Similar to `test_lore_available_at_1_cp`, but when a lore has
    been granted via the option bonus router. For some reason this
    can impact the results.
    """
    # Mages get a free Lore skill as a starting skill.
    # This is handled by the Option Bonus Router system,
    # which
    assert character.apply("mage:2")
    assert character.apply(
        ChoiceMutation(id="lore", choice="__option__", value="lore+Arcane")
    )

    assert character.apply("sharp-mind")
    assert character.apply("lore+Religious")
    assert character.apply("lore+Climate")
    assert character.apply("lore+Jokes")
    assert character.apply("lore+Mixology")
    assert character.cp.value == 1
    features = character.list_features(type="skill", taken=False, available=True)
    feature_ids = [f.full_id for f in features]
    assert "lore" in feature_ids
