from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_load_controllers(character: TempestCharacter):
    """This test triest to load all defined features into their designated controllers.

    The assert in this test is unlikely to fail, but the assert in the FeatureController constructor
    could trip if the binding that selects a constructor in CharacterController._new_controller
    is misconfigured.
    """
    for feature_id in character.ruleset.features:
        assert character.controller(feature_id)
