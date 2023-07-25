from __future__ import annotations

import pytest

from camp.engine.rules.base_models import RankMutation
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter


@pytest.fixture
def starter(character: TempestCharacter) -> TempestCharacter:
    assert character.apply("wizard:2")
    return character


def test_add_basic_skill(starter: TempestCharacter):
    assert starter.can_purchase("basic-skill")
    assert starter.apply("basic-skill")
    assert starter.meets_requirements("basic-skill")


def test_basic_cp_math(starter: TempestCharacter):
    # Starting CP is 1 + 2*Level
    assert starter.cp.value == 5
    # If we add some CP...
    starter.awarded_cp = 5
    assert starter.cp.value == 10
    # If we spend CP (basic-skill costs 1 CP)
    starter.apply("basic-skill")
    assert starter.cp.value == 9
    # Purchase more ranks...
    assert starter.apply("basic-skill:9")
    assert starter.cp.value == 0
    # Can't purchase any more due to CP cost
    assert not starter.can_purchase("basic-skill")


def test_remove_skill(starter: TempestCharacter):
    starter.apply("basic-skill")
    assert starter.can_purchase("basic-skill:-1")
    assert starter.apply("basic-skill:-1")
    assert not starter.meets_requirements("basic-skill")


def test_one_requirement_missing(starter: TempestCharacter):
    assert not starter.can_purchase("one-requirement")
    assert not starter.apply("one-requirement")


def test_two_requirements_missing(starter: TempestCharacter):
    assert not starter.can_purchase("two-requirements")
    assert not starter.apply("two-requirements")


def test_two_requirements_met(starter: TempestCharacter):
    starter.awarded_cp = 25
    assert starter.apply("basic-skill")
    assert starter.apply("one-requirement")
    assert not starter.can_purchase("two-requirements")
    assert starter.apply("granted-skill")
    assert starter.apply("two-requirements")


def test_two_requirements_met_via_grant(starter: TempestCharacter):
    starter.awarded_cp = 30
    starter.apply("basic-skill")
    starter.apply("one-requirement")
    starter.apply("grants-skill")
    assert starter.apply("two-requirements")


def test_one_requirement_met(starter: TempestCharacter):
    starter.awarded_cp = 30
    starter.apply("basic-skill")
    assert starter.can_purchase("one-requirement")
    assert starter.apply("one-requirement")


@pytest.mark.xfail
def test_remove_requirement(starter: TempestCharacter):
    """You can't sell back a skill if another skill depends on it."""
    starter.apply("basic-skill")
    starter.apply("one-requirement")
    assert not starter.can_purchase("basic-skill:-1")
    assert not starter.apply("basic-skill:-1")


def test_erroneous_option_provided(starter: TempestCharacter):
    """Skill can't be added with an option if it does not define options."""
    entry = RankMutation(id="basic-skill", option="Foo")
    assert not starter.can_purchase(entry)
    assert not starter.apply(entry)


def test_option_values_required_freeform_prohibited(starter: TempestCharacter):
    """If a skill option requires values, the option must be in that list."""
    entry = RankMutation(id="specific-options", option="Fifty Two")
    assert not starter.can_purchase(entry)
    assert not starter.apply(entry)


def test_option_values_required_freeform_allowed(starter: TempestCharacter):
    """If a skill option requires values, the option must be in that list."""
    entry = RankMutation(id="free-text", option="Fifty Two")
    assert starter.can_purchase(entry)
    assert starter.apply(entry)


def test_option_values_provided(starter: TempestCharacter):
    """If a skill option requires values, an option from that list works."""
    entry = RankMutation(id="specific-options", option="Two")
    assert starter.can_purchase(entry)
    assert starter.apply(entry)


def test_option_single_allowed(starter: TempestCharacter):
    """If a skill allows an option but does not allow multiple selection...

    Only accept a single skill entry for it.
    """
    entry = RankMutation(id="single-option", option="Rock")
    assert starter.can_purchase(entry)
    assert starter.apply(entry)
    rd = starter.can_purchase("single-option")
    assert not rd and not rd.needs_option
    assert not starter.can_purchase("single-option+Paper")


def test_option_values_flag(starter: TempestCharacter):
    """If a skill with a value option specifies a values flag, additional legal values
    can be passed in via that metadata flag.
    """
    starter.model.metadata.flags["More Specific Options"] = ["Four", "Five", "Six"]
    entry = RankMutation(id="specific-options", option="Five")
    assert starter.can_purchase(entry)
    assert starter.apply(entry)


def test_multiple_option_skill_without_option(starter: TempestCharacter):
    """If a multiple-purchase skill (no freeform) requires an option,

    1) can_add_feature returns true if it isn't given an option, but
        it returns false if all options are exhausted
    2) Even if it returns true, add_feature fails if the option is left out.

    The return value of can_add_feature will indicate that an option is needed.
    """
    fid = "specific-options"
    rd = starter.can_purchase(fid)
    assert rd.success and rd.needs_option
    assert not starter.apply(fid)
    assert starter.apply(RankMutation(id=fid, option="One"))
    assert starter.apply(RankMutation(id=fid, option="Two"))
    rd = starter.can_purchase(fid)
    assert rd.success and rd.needs_option
    rd = starter.apply(fid)
    assert not rd.success and rd.needs_option
    assert starter.apply(RankMutation(id=fid, option="Three"))
    assert not starter.can_purchase(fid)
    options = starter.get_options(fid)
    assert options == {"One": 1, "Two": 1, "Three": 1}


def test_freeform_with_suggestions_allowed(starter: TempestCharacter):
    """
    If a skill allows freeform options and specifies suggestions, the suggestions
    not taken are the only thing that appears in the "available" list.
    """
    fid = "free-text-with-suggestions"
    # Rock is in the default list...
    assert starter.apply(RankMutation(id=fid, option="Rock"))
    # Dynamite is not.
    assert starter.apply(RankMutation(id=fid, option="Dynamite"))
    fc = starter.feature_controller(fid)
    assert fc.available_options == ["Paper", "Scissors"]


def test_inherited_option_skill(starter: TempestCharacter):
    """A feature with an inherited option specified can only take values for
    that option if the option has already been taken for the inherited feature.

    i.e. you can't take "Profession - Journeyman [Fisherman]" without having taken
    "Profession - Apprentice [Fisherman]".
    """
    assert not starter.can_purchase("inherited-option+One")

    assert starter.apply("specific-options+One")

    assert starter.can_purchase("inherited-option")
    assert starter.apply("inherited-option")
    inherited = starter.feature_controller("inherited-option")
    assert inherited.option == "One"

    # After purchasing all available options, the skill no longer registers as purchasable
    rd = starter.can_purchase("inherited-option")
    assert not rd.success
    assert not rd.needs_option


def test_skill_with_option_requirements(starter: TempestCharacter):
    starter.awarded_cp = 5
    assert not starter.options_values_for_feature("requires-option")

    starter.apply("basic-skill")
    assert starter.options_values_for_feature("requires-option") == {"One"}
    assert starter.can_purchase("requires-option+One")
    assert not starter.can_purchase("requires-option+Two")

    starter.apply("basic-skill")
    assert starter.options_values_for_feature("requires-option") == {"One", "Two"}
    assert starter.can_purchase("requires-option+Two")
    assert not starter.can_purchase("requires-option+Three")

    starter.apply("basic-skill")
    assert starter.options_values_for_feature("requires-option") == {
        "One",
        "Two",
        "Three",
    }
    assert starter.apply("requires-option+Three")


def test_skill_with_one_grant(starter: TempestCharacter):
    initial_cp = starter.cp.value
    assert starter.can_purchase("grants-skill")
    assert starter.apply("grants-skill")
    # grants-skill costs 4 CP
    assert initial_cp - starter.cp.value == 4
    assert starter.meets_requirements("grants-skill")
    assert starter.meets_requirements("granted-skill")


def test_skill_with_one_grant_sellback(starter: TempestCharacter):
    starter.apply("wizard:2")
    assert not starter.meets_requirements("granted-skill")
    starter.apply("grants-skill")
    assert starter.meets_requirements("granted-skill")
    assert starter.apply("grants-skill:-1")
    assert not starter.meets_requirements("granted-skill")
