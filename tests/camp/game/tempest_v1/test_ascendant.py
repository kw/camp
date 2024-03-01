from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_temporal_awareness_can_increase(character: TempestCharacter):
    character.freeplay_cp = 2
    assert character.apply("cleric:2")
    assert character.apply("ascendant")
    assert character.apply("rewind")
    assert character.apply("temporal-manipulation")
    assert character.cp.value == 2
    assert character.can_purchase("temporal-awareness")
    assert character.apply("temporal-awareness")


def test_temporal_awareness_available(character: TempestCharacter):
    character.freeplay_cp = 2
    assert character.apply("cleric:2")
    assert character.apply("ascendant")
    assert character.apply("rewind")
    assert character.apply("temporal-manipulation")
    ascendant = character.feature_controller("ascendant")
    subfeatures = [f.id for f in ascendant.subfeatures_available]
    assert "temporal-awareness" in subfeatures
