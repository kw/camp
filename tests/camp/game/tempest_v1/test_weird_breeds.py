from camp.engine.rules.base_models import ChoiceMutation
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def canChooseAncestor(character: TempestCharacter, feature_id: str) -> bool:
    fc = character.feature_controller("ancestor-manifested")
    if cc := fc.choices.get("advantage"):
        choices = cc.available_choices()
        return feature_id in choices
    return False


def canChooseLostLife(character: TempestCharacter, feature_id: str) -> bool:
    fc = character.feature_controller("lost-life")
    if cc := fc.choices.get("borrowed-challenge"):
        choices = cc.available_choices()
        return feature_id in choices
    return False


def test_ancestor_manifested(character: TempestCharacter):
    assert character.apply("rahkdari")
    assert character.apply("not-long-for-this-world")  # +4 BP
    assert character.apply("ancestors-dues")  # +4 BP
    assert character.apply("rahk-small-horns")  # +1 BP
    assert character.apply("ancestor-manifested")  # Variable BP
    assert character.get("bp-primary") == 9

    # The character should be able to choose Left Hand of Doom
    # as a choice within Ancestor Manifested, costing 9 Rahkdari BP.
    # This should have the side effect of granting the Arm of Brogdar
    # breed challenge without getting any BP out of it

    assert canChooseAncestor(character, "left-hand-of-doom")

    assert character.choose(
        ChoiceMutation(
            id="ancestor-manifested",
            choice="advantage",
            value="left-hand-of-doom",
        )
    )

    assert character.get("left-hand-of-doom") == 1
    assert character.get("arm-of-brogdar") == 1
    assert character.get("bp-primary") == 0


def test_ancestor_manifested_insufficient_cp(character: TempestCharacter):
    assert character.apply("rahkdari")
    assert character.apply("not-long-for-this-world")  # +4 BP
    assert character.apply("ancestor-manifested")  # Variable BP
    assert character.get("bp-primary") == 4

    assert not canChooseAncestor(character, "left-hand-of-doom")

    assert not character.choose(
        ChoiceMutation(
            id="ancestor-manifested",
            choice="advantage",
            value="left-hand-of-doom",
        )
    )

    assert character.get("left-hand-of-doom") == 0
    assert character.get("arm-of-brogdar") == 0


def test_lost_life(character: TempestCharacter):
    assert character.apply("gheist")
    assert character.apply("lost-life")
    assert character.get("bp-primary") == 0

    assert canChooseLostLife(character, "aberrant-flesh")
    assert character.choose(
        ChoiceMutation(
            id="lost-life",
            choice="borrowed-challenge",
            value="aberrant-flesh",
        )
    )

    assert character.get("bp-primary") == 4
