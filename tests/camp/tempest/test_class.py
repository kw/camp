from __future__ import annotations

from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_fighter(character: TempestCharacter):
    assert character.can_purchase("fighter:2")
    assert character.apply("fighter:2")
    assert character.meets_requirements("fighter:2")
    assert character.meets_requirements("martial")
    assert character.meets_requirements("martial:2")
    assert character.meets_requirements("level:2")
    assert not character.meets_requirements("caster")
    assert not character.meets_requirements("caster:2")
    assert not character.meets_requirements("arcane:2")
    assert not character.meets_requirements("divine:2")


def test_wizard(character: TempestCharacter):
    # Purchase some Wizard levels.
    assert character.can_purchase("wizard:2")
    assert character.apply("wizard:2")

    # Do various requirement tags register as expected?
    assert character.meets_requirements("wizard:2")
    assert not character.meets_requirements("martial")
    assert not character.meets_requirements("martial:2")
    assert character.meets_requirements("level:2")
    assert character.meets_requirements("caster")
    assert character.meets_requirements("caster:2")
    assert character.meets_requirements("arcane:2")
    assert not character.meets_requirements("divine:2")


def test_druid(character: TempestCharacter):
    assert character.can_purchase("druid:2")
    assert character.apply("druid:2")
    assert character.meets_requirements("druid:2")
    assert not character.meets_requirements("martial")
    assert not character.meets_requirements("martial:2")
    assert character.meets_requirements("level:2")
    assert character.meets_requirements("caster")
    assert character.meets_requirements("caster:2")
    assert not character.meets_requirements("arcane:2")
    assert character.meets_requirements("divine:2")


def test_sellback_level2(character: TempestCharacter):
    character.apply("wizard:2")
    # Can we sell class levels back (if editing is enabled)?
    # If you sell back a class level when it's your last 2 levels,
    # both will be removed, since a character can never be "level 1".
    assert character.can_purchase("wizard:-1")
    assert character.apply("wizard:-1")
    assert not character.meets_requirements("wizard:2")
    assert not character.meets_requirements("wizard")
    assert not character.meets_requirements("level:2")
    assert not character.meets_requirements("caster")
    assert not character.meets_requirements("caster:2")
    assert not character.meets_requirements("arcane")
    assert not character.meets_requirements("arcane:2")


def test_sellback_level5(character: TempestCharacter):
    # A level 5 wizard sells back 3 levels.
    character.xp_level = 5
    assert character.apply("wizard:5")
    assert character.can_purchase("wizard:-3")
    assert character.apply("wizard:-3")

    # Should now be a level 2 wizard, with the appropriate tags
    assert character.meets_requirements("wizard:2")
    assert character.meets_requirements("level:2")
    assert character.meets_requirements("caster:2")
    assert character.meets_requirements("arcane:2")


def test_multiple_divine_classes(character: TempestCharacter):
    """Check some interactions that occur when you have two classes with the same casting sphere.

    Specifically, check that tags like 'caster' and 'divine' are additive.
    """
    character.xp_level = 10
    character.apply("druid:5")
    character.apply("cleric:5")

    assert character.meets_requirements("caster:10")
    assert character.meets_requirements("divine:10")


def test_multiclass(character: TempestCharacter):
    character.xp_level = 15
    assert character.apply("fighter:3")
    assert character.apply("wizard:5")
    assert character.apply("druid:7")
    assert character.meets_requirements("martial:3")
    assert character.meets_requirements("martial$3")
    assert not character.meets_requirements("martial$4")
    assert character.meets_requirements("martial<4")
    assert not character.meets_requirements("martial<3")

    assert character.meets_requirements("arcane:5")
    assert character.meets_requirements("arcane$5")
    assert not character.meets_requirements("arcane$6")
    assert character.meets_requirements("arcane<7")
    assert not character.meets_requirements("arcane<3")

    assert character.meets_requirements("divine:7")
    assert character.meets_requirements("divine$7")
    assert not character.meets_requirements("divine$8")
    assert character.meets_requirements("divine<8")
    assert not character.meets_requirements("divine<3")

    assert character.meets_requirements("caster:12")
    assert character.meets_requirements("caster<15")
    assert character.meets_requirements("caster$7")
    assert not character.meets_requirements("caster$8")

    assert character.meets_requirements("level:15")
    assert not character.meets_requirements("level$15")
    assert character.meets_requirements("level$7")
    assert character.meets_requirements("level<16")


def test_multiclass_sellback(character: TempestCharacter):
    """Test sellback behavior when multiclassed.

    Specifically, since the character gets its starting proficiencies
    based on its starting class, the starting class can't be removed
    from the sheet or reduced below 2 levels, even in full editing mode.
    This restriction only applies while multiclassed. If all other
    classes are removed, the starting class can also be removed.
    """
    character.xp_level = 10
    assert character.apply("wizard:5")
    assert character.apply("fighter:5")
    assert character.level == 10
    assert character.starting_class.id == "wizard"

    # You can't sell back your starting class below level 2
    # unless it's the last class you have.
    assert not character.can_purchase("wizard:-4")
    # But you can sell it back down to 2.
    assert character.can_purchase("wizard:-3")
    # You can sell back all class levels of non-starting classes.
    assert character.can_purchase("fighter:-5")
    # But not more than all, of course.
    assert not character.can_purchase("fighter:-6")

    # Actually try it.
    assert character.apply("wizard:-3")
    assert character.level == 7
    assert character.apply("fighter:-5")
    assert character.level == 2
    # Once we're down to a single class, we can buy down the rest.
    assert character.apply("wizard:-2")
    assert character.level == 0
    assert character.starting_class is None
    assert character.primary_class is None


def test_arcane_spell_slots(character: TempestCharacter):
    # TODO: Support for bonus archetype spell slots.
    character.xp_level = 7
    assert character.apply("wizard:7")
    assert character.get_prop("wizard.spell_slots") == 6
    assert character.get_prop("wizard.spell_slots@1") == 5
    assert character.get_prop("wizard.spell_slots@2") == 1
    assert character.get_prop("wizard.spell_slots@3") == 0
    assert character.get_prop("arcane.spell_slots") == 6
    assert character.get_prop("arcane.spell_slots@1") == 5
    assert character.get_prop("divine.spell_slots@1") == 0


def test_divine_spell_slots(character: TempestCharacter):
    # TODO: Support for bonus archetype spell slots.
    character.xp_level = 7
    character.apply("cleric:7")
    assert character.meets_requirements("cleric.spell_slots:6")
    assert character.meets_requirements("cleric.spell_slots@1:5")
    assert character.meets_requirements("cleric.spell_slots@2:1")
    assert not character.meets_requirements("cleric.spell_slots@3")
    assert character.meets_requirements("divine.spell_slots:6")
    assert character.meets_requirements("divine.spell_slots@1:5")
    assert not character.meets_requirements("arcane.spell_slots@1")


def test_mixed_spell_slots(character: TempestCharacter):
    # TODO: Support for bonus archetype spell slots.
    character.xp_level = 14
    character.apply("cleric:7")
    character.apply("wizard:7")
    assert character.meets_requirements("wizard.spell_slots:6")
    assert character.meets_requirements("wizard.spell_slots@1:5")
    assert character.meets_requirements("wizard.spell_slots@2:1")
    assert not character.meets_requirements("wizard.spell_slots@3")
    assert character.meets_requirements("cleric.spell_slots:6")
    assert character.meets_requirements("cleric.spell_slots@1:5")
    assert character.meets_requirements("cleric.spell_slots@2:1")
    assert not character.meets_requirements("cleric.spell_slots@3")
    assert character.meets_requirements("arcane.spell_slots@1:5")
    assert character.meets_requirements("arcane.spell_slots:6")
    assert character.meets_requirements("divine.spell_slots@1:5")
    assert character.meets_requirements("divine.spell_slots:6")


def test_bonus_spell_slots(character: TempestCharacter):
    assert character.apply("wizard:2")
    character.awarded_cp = 10
    novice_slots = character.get_prop("arcane.spell_slots@1")
    assert novice_slots > 0
    intermediate_slots = character.get_prop("arcane.spell_slots@2")
    assert intermediate_slots == 0
    assert character.apply("bonus-novice-arcane")
    # The arcane sphere itself is not modified by the bonus.
    assert character.get_prop("arcane") == 2
    # Novice slots are increased, but intermediate slots are not.
    assert character.get_prop("arcane.spell_slots@1") == novice_slots + 1
    assert character.get_prop("arcane.spell_slots@2") == intermediate_slots
    # Adding more ranks adds more novice slots.
    assert character.apply("bonus-novice-arcane")
    assert character.get_prop("arcane.spell_slots@1") == novice_slots + 2
    assert character.apply("bonus-novice-arcane")
    assert character.get_prop("arcane.spell_slots@1") == novice_slots + 3
    # Bonus intermediate slots also work. Level up to find out...
    character.xp_level = 6
    character.apply("wizard:4")
    intermediate_slots = character.get_prop("arcane.spell_slots@2")
    assert character.apply("bonus-intermediate-arcane:2")
    assert character.get_prop("arcane.spell_slots@2") == intermediate_slots + 2
