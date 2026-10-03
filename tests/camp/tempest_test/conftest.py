"""Shared fixtures for Tempest engine tests."""

import pathlib
from typing import cast

import pytest

from camp.engine import loader
from camp.engine.rules.base_engine import Engine
from camp.engine.rules.tempest.controllers.character_controller import TempestCharacter
from camp.engine.rules.tempest.engine import TempestEngine

RULESET_PATH = pathlib.Path(__file__).parent.parent / "rulesets"


@pytest.fixture
def engine() -> TempestEngine:
    engine = cast(
        TempestEngine, loader.load_ruleset(RULESET_PATH / "tempest_test").engine
    )
    assert engine.ruleset.bad_defs == []
    return engine


@pytest.fixture
def character(engine: Engine) -> TempestCharacter:
    return cast(TempestCharacter, engine.new_character())
