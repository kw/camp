from __future__ import annotations

import math
from typing import ClassVar
from typing import Iterable
from typing import Literal
from typing import Type
from typing import TypeAlias

import pydantic
from pydantic import Field
from pydantic import NonNegativeInt

from camp.engine.rules import base_models
from camp.engine.utils import maybe_iter
from camp.engine.utils import table_lookup

from . import models

Attribute: TypeAlias = base_models.Attribute


class Discount(base_models.BaseModel):
    """Describes a cost discount, generally for CP.

    Attributes:
        modifier: The amount to change the cost. For example, `1` means "the feature
            costs 1 CP less per rank".
        minimum: The minimum cost (per rank). If it's a discount, usually 1 or 0.
        ranks: The number of ranks that this can apply to.
    """

    discount: pydantic.PositiveInt
    minimum: int = 1
    ranks: int | None = None

    @classmethod
    def cast(cls, discount: Discount | int) -> Discount:
        if isinstance(discount, int):
            return cls(discount=discount)
        return discount


class GrantDef(base_models.BaseModel):
    """Describes how a grant operates in more detail."""

    id: str
    value: int | list[str] | dict[int, int] = 1
    per_rank: bool = False


Grantable: TypeAlias = str | list[str] | dict[str, int] | GrantDef
Discounts: TypeAlias = dict[str, Discount | int]


class ChoiceDef(base_models.BaseModel):
    """Describes a choice that can be made related to a feature.

    Choices are always represented by features, which might be subfeatures
    rather than "normal" features. By default, a choice causes the feature
    to be Granted, unless a discount is specified (see the `discount` attribute).
    However, a custom controler could alter this behavior.

    Attributes:
        name: The user-visible name of the choice.
        description: A user-visible description of the choice.
        limit: The number of times this choice can be made. If "unlimited",
            there is no limit.
        discount: A discount that applies to the choice. This is rarely used,
            but can be used to make a choice cheaper than normal. For example,
            the Geas Core "Patron" perk allows a number of choices to be made
            from (almost) the full list of Perks, and each choice is discounted
            by 1 CP. The choice can be made after the purchase was made. Note
            that this doesn't actually _grant_ the choice in this case.
        matcher: A feature matcher that can be used to limit the choices available.
    """

    name: str
    description: str | None = None
    limit: int | Literal["unlimited"] = 1
    discount: Discount | int | None = None
    matcher: base_models.FeatureMatcher | None = None


class BaseFeatureDef(base_models.BaseFeatureDef):
    grants: Grantable | None = None
    discounts: dict[str, Discount | int] | None = None
    choices: dict[str, ChoiceDef] | None = None

    def post_validate(self, ruleset: base_models.BaseRuleset) -> None:
        super().post_validate(ruleset)
        if self.grants:
            ruleset.validate_identifiers(_grantable_identifiers(self.grants))
        if self.discounts:
            ruleset.validate_identifiers(self.discounts.keys())
        if self.choices:
            for choice_def in self.choices.values():
                if choice_def.matcher and choice_def.matcher.id:
                    ruleset.validate_identifiers(choice_def.matcher.id)


class SubFeatureDef(BaseFeatureDef):
    type: Literal["subfeature"] = "subfeature"


class ClassDef(BaseFeatureDef):
    type: Literal["class"] = "class"
    sphere: Literal["arcane", "divine", "martial"] = "martial"
    starting_features: Grantable | None = None
    multiclass_features: Grantable | None = None
    bonus_features: dict[int, Grantable] | None = None
    # By default, classes have 10 levels.
    ranks: int = 10

    def post_validate(self, ruleset: base_models.BaseRuleset) -> None:
        super().post_validate(ruleset)
        if self.starting_features:
            ruleset.validate_identifiers(_grantable_identifiers(self.starting_features))
        if self.multiclass_features:
            ruleset.validate_identifiers(
                _grantable_identifiers(self.multiclass_features)
            )
        if self.bonus_features:
            grantables = list(self.bonus_features.values())
            ruleset.validate_identifiers(_grantable_identifiers(grantables))


class CostByRank(base_models.BaseModel):
    """For when the cost of something depends on something.

    Attributes:
        rank: Map of rank to costs. Any value that isn't map assumes
        the next lowest cost. For example:
                1: 1
                5: 3
                10: 5
            means: Ranks from 1-4 cost 1 point each. Ranks from 5-9 cost 3.
                Ranks 10+ cost 5.
    """

    ranks: dict[int, int]

    def single_rank_cost(self, rank: int) -> int:
        """The cost of a particular rank."""
        return table_lookup(self.ranks, rank)

    def rank_costs(self, ranks: int) -> list[int]:
        return [self.single_rank_cost(r) for r in range(1, ranks + 1)]


CostDef: TypeAlias = int | CostByRank | None


class SkillDef(BaseFeatureDef):
    type: Literal["skill"] = "skill"
    category: str = "General Skills"
    cost: CostDef
    uses: int | None = None
    rank_labels: dict[int, str] | None = None


class FlawDef(BaseFeatureDef):
    """
    Attributes:
        award: A value or map of values that indicate the CP award to grant
            for taking this flaw. Note that if a flaw is inflicted by plot,
            it will generally provide no CP award, but the plot member should
            still choose an appropriate award level since the flaw correction.
            If a dictionary is specified, the keys are descriptive text that can
            be selected from as though they were options. If the key begins with
            a "$" character, the rest of the key is assumed to be a flag and will
            be expanded.
    """

    type: Literal["flaw"] = "flaw"
    category: str = "General Flaws"
    award: int | dict[str, int] = Field(default=0)
    award_mods: dict[str, int] | None = None

    @property
    def option(self) -> base_models.OptionDef | None:
        if self.option_def:
            return self.option_def
        if isinstance(self.award, dict):
            return base_models.OptionDef(
                values=set(self.award.keys()),
            )
        return None

    def post_validate(self, ruleset: base_models.BaseRuleset) -> None:
        super().post_validate(ruleset)
        if self.award_mods:
            ruleset.validate_identifiers(self.award_mods.keys())


class PerkDef(BaseFeatureDef):
    type: Literal["perk"] = "perk"
    category: str = "General Perks"
    cost: CostDef
    rank_labels: dict[int, str] | None = None
    creation_only: bool = False


class PowerDef(BaseFeatureDef):
    type: Literal["power"] = "power"
    sphere: Literal["arcane", "divine", "martial", None] = None
    tier: NonNegativeInt | None = None
    class_: str | None = Field(alias="class", default=None)
    incant_prefix: str | None = None
    incant: str | None = None
    call: str | None = None
    accent: str | None = None
    target: str | None = None
    duration: str | None = None
    delivery: str | None = None
    refresh: str | None = None
    effect: str | None = None

    def post_validate(self, ruleset: base_models.BaseRuleset) -> None:
        super().post_validate(ruleset)
        ruleset.validate_identifiers(self.class_)
        ruleset.validate_identifiers(_grantable_identifiers(self.grants))


FeatureDefinitions: TypeAlias = (
    ClassDef | SubFeatureDef | SkillDef | PowerDef | FlawDef | PerkDef
)


class ScalingTable(base_models.Table, base_models.BaseModel):
    base: int
    factor: float
    rounding: Literal["up", "down", "nearest"] = "nearest"
    low: int = 1
    high: int = 25

    def bounds(self) -> tuple[int, int]:
        return self.low, self.high

    def evaluate(self, key: int) -> int:
        x = self.base + (key / self.factor)
        if key < self.low:
            key = self.low
        elif key > self.high:
            key = self.high
        match self.rounding:
            case "up":
                return math.ceil(x)
            case "down":
                return math.floor(x)
            case _:
                return round(x)


Table = ScalingTable | base_models.DictTable


class Ruleset(base_models.BaseRuleset):
    engine_class = "camp.engine.rules.tempest.engine.TempestEngine"
    features: dict[str, FeatureDefinitions] = Field(default_factory=dict)
    breed_count_cap: int = 2
    breed_primary_bp_cap: int = 10
    breed_secondary_bp_cap: int = 5
    flaw_cp_cap: int = 5
    flaw_overcome: int = 2
    cp_baseline: int = 1
    cp_per_level: int = 2
    xp_table: Table
    lp: Table = ScalingTable(base=2, factor=5, rounding="up")
    spikes: Table = ScalingTable(base=2, factor=6, rounding="down")
    # Actual rulesets will need to specify their power tables. The
    # scaling table isn't smart enough to represent whatever formula
    # the ruleset is using.
    powers: dict[int, Table] = {
        0: ScalingTable(base=0, factor=2, rounding="down"),
        1: ScalingTable(base=1, factor=2, rounding="down"),
        2: ScalingTable(base=0, factor=6, rounding="down"),
        3: ScalingTable(base=0, factor=11, rounding="down"),
        4: ScalingTable(base=0, factor=16, rounding="down"),
    }
    spells_known: Table = ScalingTable(base=1, factor=1)
    spells_prepared: Table = ScalingTable(base=1, factor=1)

    attributes: ClassVar[Iterable[Attribute]] = [
        Attribute(
            id="xp",
            name="Experience Points",
            abbrev="XP",
            description="You earn 2 XP per half-day game, or 8 per normal weekend game.",
            default_value=0,
        ),
        Attribute(
            id="xp_level",
            name="Experience Level",
            abbrev="Level",
            default_value=2,
            description="Your level, determined by your XP total.",
        ),
        Attribute(id="level", name="Character Level", hidden=True, is_tag=True),
        Attribute(id="lp", name="Life Points", abbrev="LP", default_value=2),
        Attribute(id="cp", name="Character Points", abbrev="CP", default_value=0),
        Attribute(id="breedcap", name="Max Breeds", default_value=2, hidden=True),
        Attribute(id="bp", name="Breed Points", scoped=True, default_value=0),
        Attribute(id="spikes", name="Spikes", default_value=0),
        Attribute(id="utilities", name="Utilities", scoped=True),
        Attribute(id="cantrips", name="Cantrips", scoped=True),
        Attribute(
            id="spell_slots",
            name="Spell Slots",
            scoped=True,
            tiered=True,
            tier_names=["Novice", "Intermediate", "Greater", "Master"],
        ),
        Attribute(
            id="spells_known",
            name="Spells Known",
            scoped=True,
        ),
        Attribute(
            id="spells_prepared",
            name="Spells Prepared",
            scoped=True,
        ),
        Attribute(
            id="powers",
            name="Powers",
            scoped=True,
            tiered=True,
            tier_names=["Basic", "Advanced", "Veteran", "Champion"],
        ),
        Attribute(
            id="arcane",
            name="Arcane",
            is_tag=True,
            hidden=True,
        ),
        Attribute(
            id="divine",
            name="Divine",
            is_tag=True,
            hidden=True,
        ),
        Attribute(
            id="martial",
            name="Martial",
            is_tag=True,
            hidden=True,
        ),
        Attribute(
            id="caster",
            name="Caster Levels",
            is_tag=True,
            hidden=True,
        ),
    ]

    def feature_model_types(self) -> base_models.ModelDefinition:
        return FeatureDefinitions  # type: ignore[return-value]

    @property
    def sheet_type(self) -> Type[base_models.CharacterModel]:
        return models.CharacterModel


def _grantable_identifiers(grantables: Grantable | Iterable[Grantable]) -> set[str]:
    id_set = set()
    for g in maybe_iter(grantables):
        match g:  # type: ignore
            case list():
                id_set.update(_grantable_identifiers(g))
            case dict():
                id_set.update(list(g.keys()))
            case str():
                id_set.add(g)
            case GrantDef(id=expr):
                id_set.add(expr)
            case None:
                pass
            case _:
                raise NotImplementedError(f"Unexpected grantable type {type(g)}")
    return id_set
