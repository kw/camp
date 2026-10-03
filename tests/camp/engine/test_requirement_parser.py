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
        "feature-id+Text",
        "feature-id:5",
        "feature-id@5",
        "feature-id<5",
        "feature-id+Text:5",
        "feature-id@4:5",
        "feature-id+Undead_Lore",
        "feature-id.attribute",
        "feature-id@1+My_Option:2$3<4",
        "feature-id.attribute@1+My_Option:2$3<4",
        "feature_id.attribute_id",
        "accent-substantiation+Agony_➡_Acid",
    ],
)
def test_parse_propreq(req):
    """Test that parsing and serializing work and have the same representation.

    In other words, each of the listed strings should parse successfully
    and serialize back to the original string.
    """
    assert (p := PropExpression.parse(req))
    assert repr(p) == req


def test_parse_propreq_values():
    """Test that, when parsed, the PropReq has the expected values."""
    p = PropExpression.parse("foo.bar+baz.attr@1+My_Option:23$34<450")
    assert p.prefixes == ("foo", "bar+baz")
    assert p.prop == "attr"
    assert p.slot == 1
    assert p.option == "My Option"
    assert p.value == 23
    assert p.single == 34
    assert p.less_than == 450


def test_parse_req():
    req = [
        "feature-id+Text",
        {
            "all": [
                "one",
                "two",
                "-three",
            ],
        },
        {
            "any": [
                "four:4",
                "five$5",
                {"all": ["six@6"]},
            ]
        },
        {
            "none": [
                "seven+?",
                "eight<8",
            ]
        },
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
