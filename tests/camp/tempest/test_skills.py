from __future__ import annotations

import pytest

from camp.engine.rules.base_models import RankMutation
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


def test_add_basic_skill(character: TempestCharacter):
    assert character.can_purchase("basic-skill")
    assert character.apply("basic-skill")
    assert character.meets_requirements("basic-skill")


def test_basic_cp_math(character: TempestCharacter):
    # Starting CP is 1 + 2*Level
    assert character.cp.value == 5
    # If we add some CP...
    character.awarded_cp = 5
    assert character.cp.value == 10
    # If we spend CP (basic-skill costs 1 CP)
    character.apply("basic-skill")
    assert character.cp.value == 9
    # Purchase more ranks...
    assert character.apply("basic-skill:9")
    assert character.cp.value == 0
    # Can't purchase any more due to CP cost
    assert not character.can_purchase("basic-skill")


def test_remove_skill(character: TempestCharacter):
    character.apply("basic-skill")
    assert character.can_purchase("basic-skill:-1")
    assert character.apply("basic-skill:-1")
    assert not character.meets_requirements("basic-skill")


def test_one_requirement_missing(character: TempestCharacter):
    assert not character.can_purchase("one-requirement")
    assert not character.apply("one-requirement")


def test_two_requirements_missing(character: TempestCharacter):
    assert not character.can_purchase("two-requirements")
    assert not character.apply("two-requirements")


def test_two_requirements_met(character: TempestCharacter):
    character.awarded_cp = 25
    assert character.apply("basic-skill")
    assert character.apply("one-requirement")
    assert not character.can_purchase("two-requirements")
    assert character.apply("granted-skill")
    assert character.apply("two-requirements")


def test_two_requirements_met_via_grant(character: TempestCharacter):
    character.awarded_cp = 9
    character.apply("basic-skill")
    character.apply("one-requirement")
    character.apply("grants-skill")
    assert character.apply("two-requirements")


def test_one_requirement_met(character: TempestCharacter):
    character.apply("basic-skill")
    assert character.can_purchase("one-requirement")
    assert character.apply("one-requirement")


@pytest.mark.xfail
def test_remove_requirement(character: TempestCharacter):
    """You can't sell back a skill if another skill depends on it."""
    character.apply("basic-skill")
    character.apply("one-requirement")
    assert not character.can_purchase("basic-skill:-1")
    assert not character.apply("basic-skill:-1")


def test_erroneous_option_provided(character: TempestCharacter):
    """Skill can't be added with an option if it does not define options."""
    entry = RankMutation(id="basic-skill", option="Foo")
    assert not character.can_purchase(entry)
    assert not character.apply(entry)


def test_option_values_required_freeform_prohibited(character: TempestCharacter):
    """If a skill option requires values, the option must be in that list."""
    entry = RankMutation(id="specific-options", option="Fifty Two")
    assert not character.can_purchase(entry)
    assert not character.apply(entry)


def test_option_values_required_freeform_allowed(character: TempestCharacter):
    """If a skill option requires values, the option must be in that list."""
    entry = RankMutation(id="free-text", option="Fifty Two")
    assert character.can_purchase(entry)
    assert character.apply(entry)


def test_option_values_provided(character: TempestCharacter):
    """If a skill option requires values, an option from that list works."""
    entry = RankMutation(id="specific-options", option="Two")
    assert character.can_purchase(entry)
    assert character.apply(entry)


def test_option_single_allowed(character: TempestCharacter):
    """If a skill allows an option but does not allow multiple selection...

    Only accept a single skill entry for it.
    """
    entry = RankMutation(id="single-option", option="Rock")
    assert character.can_purchase(entry)
    assert character.apply(entry)
    assert not character.can_purchase("single-option")
    assert not character.can_purchase("single-option#Paper")


def test_option_values_flag(character: TempestCharacter):
    """If a skill with a value option specifies a values flag, additional legal values
    can be passed in via that metadata flag.
    """
    character.model.metadata.flags["More Specific Options"] = ["Four", "Five", "Six"]
    entry = RankMutation(id="specific-options", option="Five")
    assert character.can_purchase(entry)
    assert character.apply(entry)


def test_multiple_option_skill_without_option(character: TempestCharacter):
    """If a multiple-purchase skill (no freeform) requires an option,

    1) can_add_feature returns true if it isn't given an option, but
        it returns false if all options are exhausted
    2) Even if it returns true, add_feature fails if the option is left out.

    The return value of can_add_feature will indicate that an option is needed.
    """
    fid = "specific-options"
    rd = character.can_purchase(fid)
    assert not rd.success and rd.needs_option
    assert not character.apply(fid)
    assert character.apply(RankMutation(id=fid, option="One"))
    assert character.apply(RankMutation(id=fid, option="Two"))
    rd = character.can_purchase(fid)
    assert not rd.success and rd.needs_option
    assert not character.apply(fid)
    assert character.apply(RankMutation(id=fid, option="Three"))
    assert not character.can_purchase(fid)
    options = character.get_options(fid)
    assert options == {"One": 1, "Two": 1, "Three": 1}


def test_inherited_option_skill(character: TempestCharacter):
    """A feature with an inherited option specified can only take values for
    that option if the option has already been taken for the inherited feature.

    i.e. you can't take "Profession - Journeyman [Fisherman]" without having taken
    "Profession - Apprentice [Fisherman]".
    """
    assert not character.can_purchase("inherited-option#One")

    character.apply("specific-options#One")
    character.apply("specific-options#Two")

    assert character.can_purchase("inherited-option").needs_option
    assert character.options_values_for_feature(
        "inherited-option", exclude_taken=True
    ) == {"One", "Two"}
    assert character.can_purchase("inherited-option#One")
    assert character.apply("inherited-option#One")
    assert character.options_values_for_feature(
        "inherited-option", exclude_taken=True
    ) == {"Two"}
    assert character.apply("inherited-option#Two")

    # After purchasing all available options, the skill no longer registers as purchasable
    rd = character.can_purchase("inherited-option")
    assert not rd.success
    assert not rd.needs_option


def test_inherited_option_with_ranks(character: TempestCharacter):
    """If the inherited option feature is specified with a rank value, values from that feature
    are only valid choices if they have that many ranks.
    """
    character.awarded_cp = 5
    character.apply("specific-options#One")
    character.apply("specific-options#Two:4")

    assert character.can_purchase("inherited-with-ranks").needs_option
    assert character.options_values_for_feature(
        "inherited-with-ranks", exclude_taken=True
    ) == {"Two"}
    assert not character.can_purchase("inherited-with-ranks#One")
    assert character.can_purchase("inherited-with-ranks#Two")
    assert not character.apply("inherited-with-ranks#One")
    assert character.apply("inherited-with-ranks#Two")
    assert not character.options_values_for_feature(
        "inherited-with-ranks", exclude_taken=True
    )

    rd = character.can_purchase("inherited-with-ranks")
    assert not rd.success
    assert not rd.needs_option


def test_skill_with_option_requirements(character: TempestCharacter):
    character.awarded_cp = 5
    assert not character.options_values_for_feature("requires-option")

    character.apply("basic-skill")
    assert character.options_values_for_feature("requires-option") == {"One"}
    assert character.can_purchase("requires-option#One")
    assert not character.can_purchase("requires-option#Two")

    character.apply("basic-skill")
    assert character.options_values_for_feature("requires-option") == {"One", "Two"}
    assert character.can_purchase("requires-option#Two")
    assert not character.can_purchase("requires-option#Three")

    character.apply("basic-skill")
    assert character.options_values_for_feature("requires-option") == {
        "One",
        "Two",
        "Three",
    }
    assert character.apply("requires-option#Three")


def test_skill_with_one_grant(character: TempestCharacter):
    initial_cp = character.cp.value
    assert character.can_purchase("grants-skill")
    assert character.apply("grants-skill")
    # grants-skill costs 4 CP
    assert initial_cp - character.cp.value == 4
    assert character.meets_requirements("grants-skill")
    assert character.meets_requirements("granted-skill")


def test_skill_with_one_grant_sellback(character: TempestCharacter):
    assert not character.meets_requirements("granted-skill")
    character.apply("grants-skill")
    assert character.meets_requirements("granted-skill")
    assert character.apply("grants-skill:-1")
    assert not character.meets_requirements("granted-skill")
