from __future__ import annotations

import pathlib
import shutil
from importlib import resources

import pytest

from camp.engine import loader
from camp.engine import utils

RULESET_PATH = pathlib.Path(__file__).parent.parent / "rulesets"
TEMPEST_TEST = RULESET_PATH / "tempest_test"

PATH_PARAMS = [
    pytest.param(TEMPEST_TEST, id="dir-test"),
    pytest.param("$tests.camp.rulesets.tempest_test", id="resource-test"),
]

FAIL_TEMPLATE = """
Could not parse {path}

Parse failed with {exception_type}:
{exception_message}

Parsed data:
{data}
"""


@pytest.mark.parametrize("path", PATH_PARAMS)
def test_load_ruleset(path):
    """Very basic loader test.

    1. Does the load return with no bad defs?
    2. Are features loaded?

    Other tests will cover more specific cases.
    """
    ruleset = loader.load_ruleset(path)
    if ruleset.bad_defs:
        bd = ruleset.bad_defs[0]
        if bd.data:
            bd.data["description"] = "<...>"
            data = utils.dump_json(bd.data, sort_keys=True, indent=4)
        else:
            data = None
        pytest.fail(
            FAIL_TEMPLATE.format(
                path=bd.path,
                exception_type=bd.exception_type,
                exception_message=bd.exception_message,
                data=data,
            ),
            pytrace=False,
        )
    assert ruleset.features


@pytest.mark.parametrize("path", PATH_PARAMS)
@pytest.mark.parametrize("format", ["zip"])
def test_load_archive_ruleset(path, format, tmp_path_factory):
    """Zipfile loader test."""
    archive_path = str(path)
    if archive_path.startswith("$"):
        archive_path = resources.files(archive_path[1:])
    temp_base = tmp_path_factory.mktemp("camp-engine-test") / "ruleset"
    archive = shutil.make_archive(temp_base, format, root_dir=archive_path)
    ruleset = loader.load_ruleset(archive)
    assert not ruleset.bad_defs
    assert ruleset.features


@pytest.mark.parametrize("path", PATH_PARAMS)
def test_serialize_ruleset(path):
    """Test that the ruleset can be serialized and deserialized.

    For this to work, the ruleset must properly indicate its
    feature types on its ruleset subclass.
    """
    ruleset = loader.load_ruleset(path)
    ruleset_json = utils.dump_json(ruleset)
    assert ruleset_json
    reloaded_ruleset = loader.deserialize_ruleset(ruleset_json)
    assert reloaded_ruleset.features
    assert ruleset.model_dump() == reloaded_ruleset.model_dump()

    for fid, defn in reloaded_ruleset.features.items():
        assert defn.requires == ruleset.features[fid].requires
