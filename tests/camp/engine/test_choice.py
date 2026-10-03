from camp.engine.rules import base_models as bm


def test_choice_parse():
    m = bm.ChoiceMutation.parse("foo!bar=baz")

    assert m.id == "foo"
    assert m.choice == "bar"
    assert m.value == "baz"
    assert not m.remove
    assert m.expression == "foo!bar=baz"


def test_neg_choice_parse():
    m = bm.ChoiceMutation.parse("-foo-bar!baz_lol=kaboom")

    assert m.id == "foo-bar"
    assert m.choice == "baz_lol"
    assert m.value == "kaboom"
    assert m.remove
