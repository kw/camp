from camp.engine.rules.base_models import ChoiceMutation
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


class TestIndividualDiscount:
    """Individual discounts applied to specific lores."""

    def test_culture_discount(self, character: TempestCharacter):
        assert character.apply("artisan:2")
        assert character.apply("edosite")
        assert character.cp.value == 5
        # Edosite discounts Lore: Noble
        assert character.apply("lore+Noble")
        assert character.cp.value == 4
        # Other lores are not discounted
        assert character.apply("lore+Fish")
        assert character.cp.value == 2

    def test_lore_available_at_1_cp(self, character: TempestCharacter):
        assert character.apply("artisan:2")
        assert character.apply("edosite")
        assert character.apply("lore+Databases")
        assert character.apply("lore+Python")
        assert character.cp.value == 1
        features = character.list_features(type="skill", taken=False, available=True)
        feature_ids = [f.full_id for f in features]
        assert "lore+Noble" in feature_ids
        assert "lore" not in feature_ids

    def test_lore_purchase_at_1_cp(self, character: TempestCharacter):
        assert character.apply("artisan:2")
        assert character.apply("edosite")
        assert character.apply("lore+Databases")
        assert character.apply("lore+Python")
        assert character.cp.value == 1
        assert character.apply("lore+Noble")


class TestSharpMind:
    """Global discounts applied to the 'lore' skill."""

    def test_sharp_mind_discount(self, character: TempestCharacter):
        """Lore discounts are applied as expected."""
        assert character.apply("artisan:2")
        assert character.apply("sharp-mind")
        assert character.cp.value == 2
        assert character.apply("lore+Arcane")
        assert character.cp.value == 1

    def test_lore_available_at_1_cp(self, character: TempestCharacter):
        """Lore appears in the Skills Available list at 1 CP."""
        assert character.apply("artisan:2")
        assert character.apply("sharp-mind")
        assert character.apply("lore+Arcane")
        features = character.list_features(type="skill", taken=False, available=True)
        feature_ids = [f.full_id for f in features]
        assert "lore" in feature_ids

    def test_lore_purchase_at_1_cp(self, character: TempestCharacter):
        """Purchasing a new Lore works at 1 CP."""
        assert character.apply("artisan:2")
        assert character.apply("sharp-mind")
        assert character.apply("lore+Arcane")
        assert character.apply("lore+Religious")
        assert character.cp.value == 0

    def test_lore_available_with_granted(self, character: TempestCharacter):
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
