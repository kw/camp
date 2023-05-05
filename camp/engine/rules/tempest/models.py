from __future__ import annotations

from pydantic import Field

from .. import base_models


class FeatureModel(base_models.BaseModel):
    """Data needed to model a generic feature on a character sheet.

    Attributes:
        type: Set to the type of power (as per the feature definition's type). If a model
            subclass specifies a specific type literal (see FlawModel), that subclass model
            will be loaded instead.
        ranks: Number of ranks purchased. Ranks will be recorded here regardless of whether this
            is an option feature (in which case the distribution between options will appear in the
            `options` attribute). A feature model may be recorded with 0 ranks if it has other properties
            that may need to be recorded, typically due to granted ranks.
        notes: Notes about this feature added by the player.
        choices: If this power has choices, what has been chosen?
        options: If this power has options, what is their rank allocation? The rank allocation will not
            always add up to the value in the `ranks` field. For example, if a character has purchased
            no ranks of Lore but has 3 ranks of Lore _granted_ by another feature, the player will need
            to select which options to allocate the grants to. These selections are added to this dict
            regardless of whether the ranks come from purchases or grants.
        plot_added: Marks this power as added by plot. In some cases, sheet mechanics may vary slightly
            depending on whether plot forcibly added it.
        plot_notes: Notes about this feature added by plot. Not shown to players.
        plot_free: If true and this power comes with a cost or award (in CP or BP) then it does
            not apply here. Generally used when plot wants to grant a flaw, perk, role, etc
            as a reward or punishment.
        plot_suppressed: The power is marked off on the character sheet and no longer functions.
            This usually only happens with Patron (and perks obtained from it) and Religions.
            Powers may appear suppressed for other reasons (for example, if one of their prerequisites
            becomes suppressed or otherwise removed).
    """

    ranks: int = 0
    notes: str | None = None
    choices: dict[str, list[str]] | None = None
    plot_added: bool = False
    plot_notes: str | None = None
    plot_free: bool = False
    plot_suppressed: bool = False

    # Flaw-specific attributes
    overcome: bool = False
    plot_disable_overcome: bool = False
    overcome_award_override: int | None = None

    # Class-specific attributes
    is_archetype_class: bool = False
    is_starting_class: bool = False

    def should_keep(self) -> bool:
        """Should return True if the model has been populated with something worth saving."""
        return bool(
            self.ranks
            or self.notes
            or self.choices
            or self.plot_added
            or self.plot_notes
            or self.plot_free
            or self.plot_suppressed
            or self.overcome
            or self.plot_disable_overcome
            or self.overcome_award_override is not None
            or self.is_archetype_class
            or self.is_starting_class
        )


class CharacterModel(base_models.CharacterModel):
    features: dict[str, FeatureModel] = Field(default_factory=dict)
