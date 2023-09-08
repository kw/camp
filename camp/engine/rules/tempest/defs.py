from __future__ import annotations

import math
from typing import ClassVar
from typing import Iterable
from typing import Literal
from typing import Type
from typing import TypeAlias

from pydantic import Field
from pydantic import PositiveInt

from camp.engine.rules import base_models
from camp.engine.utils import maybe_iter
from camp.engine.utils import table_lookup

from . import models

Attribute: TypeAlias = base_models.Attribute


class GrantDef(base_models.BaseModel):
    """Describes how a grant operates in more detail."""

    id: str
    value: int | list[str] | dict[int, int] = 1
    per_rank: bool = False


Grantable: TypeAlias = str | list[str] | dict[str, int] | GrantDef
Discounts: TypeAlias = dict[str, base_models.Discount | int]


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
        limit_is_per_rank: If True, the limit is multiplied by the rank of the feature.
        matcher: A feature matcher that can be used to limit the choices available, assuming
            this choice selects a feature.
        starting_class: Only applies to basic classes. If True, the choice is only
            available when the class is your starting class.
        controller: If provided, the name of a custom controller to use for this
            choice. If not provided, the default controller is used.
        controller_args: If provided, a dictionary of arbitrary data to be used
            by the custom controller.
        multi: Allows a choice to be taken multiple times.
    """

    name: str | None = None
    description: str | None = None
    limit: int | Literal["unlimited"] = 1
    limit_is_per_rank: bool = False
    matcher: base_models.FeatureMatcher | None = None
    starting_class: bool = False
    controller: str | None = None
    controller_data: dict | None = None
    multi: bool = False


class PowerCard(base_models.BaseModel):
    name: str | None = None
    incant: str | None = None
    call: str | None = None
    accent: str | None = None
    target: str | None = None
    duration: str | None = None
    delivery: str | None = None
    refresh: str | None = None
    effect: str | None = None
    description: str | None = None

    def should_format_as_card(self) -> bool:
        return (
            self.incant
            or self.call
            or self.accent
            or self.target
            or self.duration
            or self.delivery
            or self.refresh
            or self.effect
        )


class ChildPurchaseDef(base_models.BaseModel):
    basis: str | None = None
    limit: Table | None = None


class BaseFeatureDef(base_models.BaseFeatureDef, PowerCard):
    cost: CostDef = None
    grants: Grantable | None = None
    grant_if: dict[str, base_models.Requirements] | None = None
    rank_grants: dict[int, Grantable] | None = Field(default=None, alias="level_grants")
    discounts: Discounts | None = None
    choices: dict[str, ChoiceDef] | None = None
    subcard: PowerCard | list[PowerCard] | None = None
    child_purchase: ChildPurchaseDef | None = None

    def post_validate(self, ruleset: base_models.BaseRuleset) -> None:
        super().post_validate(ruleset)
        if self.grants:
            ruleset.validate_identifiers(_grantable_identifiers(self.grants))
        if self.grant_if:
            ruleset.validate_identifiers(self.grant_if.keys())
            for grant, req in self.grant_if.items():
                # Normalize the requirements. This mirrors BaseFeatureDef.post_validate's
                # handling of the `requirements` field.
                if req := base_models.parse_req(req):
                    ruleset.validate_identifiers(list(req.identifiers()))
                    self.grant_if[grant] = req
        if self.rank_grants:
            grantables = list(self.rank_grants.values())
            ruleset.validate_identifiers(_grantable_identifiers(grantables))
        if self.discounts:
            ruleset.validate_identifiers(self.discounts.keys())
        if self.choices:
            for choice_def in self.choices.values():
                if choice_def.matcher and choice_def.matcher.id:
                    ruleset.validate_identifiers(choice_def.matcher.id)
        if self.tags:
            # Verify that all tags are declared in the ruleset.
            for tag in self.tags:
                if tag not in ruleset.tags:
                    raise ValueError(f"Tag `{tag}` is not defined in the ruleset.")


class SubFeatureDef(BaseFeatureDef):
    type: Literal["subfeature"] = "subfeature"
    display_type: str | None = None


class ClassDef(BaseFeatureDef):
    type: Literal["class"] = "class"
    sphere: Literal["arcane", "divine", "martial"] = "martial"
    starting_features: Grantable | None = None
    multiclass_features: Grantable | None = None
    class_type: Literal["basic", "advanced", "epic"] = "basic"

    # At time of writing, only used for Artisan specialization tags.
    specializations: set[str] | None = None

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


class SkillDef(BaseFeatureDef):
    type: Literal["skill"] = "skill"
    category: str = "General Skills"
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
                multiple=False,
            )
        return None

    def post_validate(self, ruleset: base_models.BaseRuleset) -> None:
        super().post_validate(ruleset)
        if self.award_mods:
            ruleset.validate_identifiers(self.award_mods.keys())


class PerkDef(BaseFeatureDef):
    type: Literal["perk"] = "perk"
    category: str = "General Perks"
    rank_labels: dict[int, str] | None = None
    creation_only: bool = False


class InnatePower(BaseFeatureDef):
    type: Literal["innate"] = "innate"


class ArchetypePower(BaseFeatureDef):
    type: Literal["archetype"] = "archetype"


class Power(BaseFeatureDef):
    type: Literal["power"] = "power"
    tier: PositiveInt | None = None


class Utility(BaseFeatureDef):
    type: Literal["utility"] = "utility"


class Spell(BaseFeatureDef):
    type: Literal["spell"] = "spell"
    tier: PositiveInt | None = None
    sphere: Literal["arcane", "divine", None] = None


class Cantrip(BaseFeatureDef):
    type: Literal["cantrip"] = "cantrip"
    sphere: Literal["arcane", "divine", None] = None


class Culture(BaseFeatureDef):
    type: Literal["culture"] = "culture"


class InheritancePower(BaseFeatureDef):
    type: Literal["inheritance"] = "inheritance"


class Religion(BaseFeatureDef):
    type: Literal["religion"] = "religion"


class DevotionPower(BaseFeatureDef):
    type: Literal["devotion"] = "devotion"
    level: Literal["bonus", "basic", "advanced"]
    parent: str  # Parent is _required_


class Breed(BaseFeatureDef):
    type: Literal["breed"] = "breed"


class Subbreed(BaseFeatureDef):
    type: Literal["subbreed"] = "subbreed"
    parent: str  # Parent is _required_


class BreedChallenge(BaseFeatureDef):
    type: Literal["breedchallenge"] = "breedchallenge"
    subbreed: str | None = None
    award: int | dict[str, int] = Field(default=0)
    award_mods: dict[str, int] | None = None
    costuming: set[str] | bool = False
    parent: str  # Parent is _required_

    @classmethod
    def default_name(cls) -> str:
        return "Breed Challenge"

    def post_validate(self, ruleset: base_models.BaseRuleset) -> None:
        super().post_validate(ruleset)
        if self.subbreed:
            ruleset.validate_identifiers(self.subbreed)

    @property
    def option(self) -> base_models.OptionDef | None:
        if self.option_def:
            return self.option_def
        if isinstance(self.award, dict):
            return base_models.OptionDef(
                values=set(self.award.keys()),
                multiple=False,
            )
        return None


class BreedAdvantage(BaseFeatureDef):
    type: Literal["breedadvantage"] = "breedadvantage"
    subbreed: str | None = None

    @classmethod
    def default_name(cls) -> str:
        return "Breed Advantage"

    def post_validate(self, ruleset: base_models.BaseRuleset) -> None:
        super().post_validate(ruleset)
        if self.subbreed:
            ruleset.validate_identifiers(self.subbreed)


FeatureDefinitions: TypeAlias = (
    ClassDef
    | SubFeatureDef
    | SkillDef
    | FlawDef
    | PerkDef
    | InnatePower
    | ArchetypePower
    | Power
    | Spell
    | Cantrip
    | Utility
    | Culture
    | InheritancePower
    | Religion
    | DevotionPower
    | Breed
    | Subbreed
    | BreedChallenge
    | BreedAdvantage
)


class Ruleset(base_models.BaseRuleset):
    engine_class: str = "camp.engine.rules.tempest.engine.TempestEngine"
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
    plural_names: dict[str, str] = {
        "Class": "Classes",
        "Utility": "Utilities",
        "Culture": "Culture",  # You only get one, so don't pluralize.
        "Religion": "Religion",  # Also only get one.
    }
    tags: dict[str, str | None] = Field(default_factory=dict)

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
        Attribute(id="breeds", name="Breeds Taken", hidden=True),
        Attribute(id="bp", name="Breed Points", abbrev="BP", default_value=0),
        Attribute(
            id="bp-primary",
            name="Breed Points (Primary)",
            abbrev="BP",
            scoped=False,
            default_value=0,
        ),
        Attribute(
            id="bp-secondary",
            name="Breed Points (Secondary)",
            abbrev="BP",
            scoped=False,
            default_value=0,
        ),
        Attribute(
            id="costuming",
            name="Costuming Points",
            scoped=True,
            hidden=True,
            default_value=0,
        ),
        Attribute(
            id="cap",
            name="BP Cap",
            scoped=True,
            hidden=True,
        ),
        Attribute(id="spikes", name="Spikes", default_value=0),
        Attribute(id="utilities", name="Utilities", scoped=True),
        Attribute(id="cantrips", name="Cantrips", scoped=True),
        Attribute(
            id="spell_slots",
            name="Spell Slots",
            scoped=True,
            tiered=True,
            tier_names=["Novice", "Adept", "Greater", "Master"],
        ),
        Attribute(
            id="spells_known",
            name="Spells Known",
            scoped=True,
        ),
        # "spell" is a global attribute that counts the number of spell slots
        # of any sphere you have available at each tier.
        Attribute(
            id="spell",
            name="Spell",
            scoped=False,
            tiered=True,
            tier_names=["Novice", "Adept", "Greater", "Master"],
        ),
        # Spellbook is a little different than Spells Known. It's a pool of "bonus" spellbook
        # capacity granted by skills like Basic Arcane, Spellscholar, etc. Spellbook capacity
        # is per-sphere, and critically, taking the Sourcerer class blocks it entirely.
        Attribute(
            id="spellbook",
            name="Spellbook",
            hidden=True,
            scoped=True,
        ),
        Attribute(
            id="powerbook",
            name="Powerbook",
            scoped=True,
            hidden=True,
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
        # Power is a global attribute that counts the number of tiered powers you know of any class.
        Attribute(
            id="power",
            name="Power",
            scoped=False,
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
        Attribute(
            id="basic-classes",
            name="Basic Classes",
            hidden=True,
        ),
        Attribute(
            id="specialization",
            name="Specialization",
            hidden=True,
            scoped=True,
        ),
        Attribute(
            id="basic",
            name="Basic",
            hidden=True,
            scoped=True,
        ),
        Attribute(
            id="advanced",
            name="Advanced",
            hidden=True,
            scoped=True,
        ),
        Attribute(
            id="devotion",
            name="Devotion Powers",
            hidden=True,
            scoped=False,
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
