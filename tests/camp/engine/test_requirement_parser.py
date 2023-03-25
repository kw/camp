from __future__ import annotations

import pytest

from camp.engine.rules.base_models import AllOf
from camp.engine.rules.base_models import AnyOf
from camp.engine.rules.base_models import NoneOf
from camp.engine.rules.base_models import PropExpression
from camp.engine.rules.base_models import parse_req


@pytest.mark.parametrize(
    "req",
    [
        "feature-id",
        "feature-id#Text",
        "feature-id:5",
        "feature-id@5",
        "feature-id<5",
        "feature-id#Text:5",
        "feature-id@4:5",
        "feature-id#Undead_Lore",
        "feature-id@1#My_Option:2$3<4",
    ],
)
def test_parse_propreq(req):
    """Test that parsing and serializing work and have the same representation.

    In other words, each of the listed strings should parse successfully
    and serialize back to the original string.
    """
    assert (p := PropExpression.parse(req))
    assert repr(p) == req


def test_prarse_propreq_values():
    """Test that, when parsed, the PropReq has the expected values."""
    p = PropExpression.parse("feature-id@1#My_Option:23$34<450")
    assert p.prop == "feature-id"
    assert p.slot == "1"
    assert p.option == "My Option"
    assert p.value == 23
    assert p.single == 34
    assert p.less_than == 450


def test_parse_req():
    req = [
        "feature-id#Text",
        AllOf(
            all=[
                "one",
                "two",
                "-three",
            ]
        ),
        AnyOf(
            any=[
                "four:4",
                "five$5",
                AllOf(all=["six@6"]),
            ]
        ),
        NoneOf(
            none=[
                "seven#?",
                "eight<8",
            ]
        ),
    ]
    parsed = parse_req(req)
    assert parsed == AllOf(
        all=[
            PropExpression(prop="feature-id", option="Text"),
            AllOf(
                all=[
                    PropExpression(prop="one"),
                    PropExpression(prop="two"),
                    NoneOf(none=[PropExpression(prop="three")]),
                ]
            ),
            AnyOf(
                any=[
                    PropExpression(prop="four", value=4),
                    PropExpression(prop="five", single=5),
                    AllOf(all=[PropExpression(prop="six", slot=6)]),
                ]
            ),
            NoneOf(
                none=[
                    PropExpression(prop="seven", option="?"),
                    PropExpression(prop="eight", less_than=8),
                ]
            ),
        ]
    )
