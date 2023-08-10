from __future__ import annotations

from functools import cached_property

from camp.engine import utils
from camp.engine.rules.decision import Decision

from .. import defs
from . import attribute_controllers
from . import character_controller
from . import feature_controller


class BreedController(feature_controller.FeatureController):
    definition: defs.Breed
    supports_child_purchases: bool = True

    @property
    def formal_name(self) -> str:
        if sbi := self.subbreed_id:
            sb_name = self.character.display_name(sbi)
            return f"{self.definition.name} [{sb_name}]"
        return self.definition.name

    @property
    def subbreed_id(self) -> str | None:
        for child in self.taken_children:
            if isinstance(child, BreedChallengeController):
                if sbi := child.subbreed_id:
                    return sbi
        return None

    @property
    def subbreed(self) -> feature_controller.FeatureController | None:
        if sbi := self.subbreed_id:
            return self.character.controller(sbi)
        return None

    @property
    def is_primary(self) -> bool:
        # TODO: Manage primary breed selection
        return True

    @property
    def taken_challenges(self) -> list[BreedChallengeController]:
        return [
            c for c in self.taken_children if isinstance(c, BreedChallengeController)
        ]

    def all_subbreeds(self) -> list[feature_controller.FeatureController]:
        return [c for c in self.children if c.feature_type == "subbreed"]

    def can_afford(self, value: int = 1) -> Decision:
        if len(self.character.breeds) < 2:
            return Decision.OK
        return Decision.NO

    def extra_grants(self) -> dict[str, int]:
        grants = super().extra_grants()
        if sbi := self.subbreed_id:
            grants[sbi] = 1
        return grants

    @property
    def explain(self) -> list[str]:
        reasons = super().explain

        if self.is_primary:
            primary_or_secondary = "primary"
            bp_attr = "bp-primary"
        else:
            primary_or_secondary = "secondary"
            bp_attr = "bp-secondary"

        bp_controller: attribute_controllers.BreedPointController = (
            self.character.attribute_controller(bp_attr)
        )
        bp_cap = bp_controller.bp_cap
        bp_awards = bp_controller.awarded_bp
        bp_challenges = bp_controller.challenge_award_bp
        bp_balance = bp_controller.value

        if subbreed := self.subbreed:
            reasons.append(
                f"Your subbreed is [{subbreed.display_name()}](../{subbreed.full_id})"
            )
            # TODO: Don't display this line after character creation.
            reasons.append(
                "To remove or change your subbreed, remove all subbreed advantages and challenges."
            )
        elif self.is_primary:
            # This advertises subbreeds available, if not yet taken.
            # TODO: Don't display this after character creation.
            reasons.append(
                "To take a subbreed, select a challenge from it. Available subbreeds:"
            )
            for subbreed in self.all_subbreeds():
                reasons.append(
                    f"[{subbreed.display_name()}](../{subbreed.full_id}): {subbreed.short_description}"
                )

        reasons.append(
            f"This is your {primary_or_secondary} breed, so your maximum Breed Points from challenges is {bp_cap}."
        )
        if bp_awards == bp_challenges:
            reasons.append(f"You have received {bp_awards} BP from challenges.")
        else:
            reasons.append(
                f"You have taken {bp_challenges} BP worth of challenges, of which you receive {bp_awards} BP."
            )
        if bp_controller.bonus:
            reasons.append(f"You have received {bp_controller.bonus} bonus BP")

        reasons.append(f"You have {bp_balance} BP to spend on breed advantages.")
        return reasons


class SubbreedController(feature_controller.FeatureController):
    definition: defs.Subbreed
    parent: BreedController | None
    _NO_TAKE = Decision(
        success=False,
        reason="To take a subbreed, choose a challenge from that subbreed.",
    )

    def __init__(self, full_id: str, character: character_controller.TempestCharacter):
        super().__init__(full_id, character)
        if not isinstance(self.definition, defs.Subbreed):
            raise ValueError(
                f"Expected {full_id} to be a subbreed but was {type(self.definition)}"
            )

    def can_afford(self, value: int = 1) -> Decision:
        if self.value:
            return Decision.NO
        return self._NO_TAKE

    def can_increase(self, value: int = 1) -> Decision:
        if self.value:
            return Decision.NO
        return self._NO_TAKE


class BreedChallengeController(feature_controller.FeatureController):
    definition: defs.BreedChallenge
    parent: BreedController | None

    def __init__(self, full_id: str, character: character_controller.TempestCharacter):
        super().__init__(full_id, character)
        if not isinstance(self.definition, defs.BreedChallenge):
            raise ValueError(
                f"Expected {full_id} to be a breed challenge but was {type(self.definition)}"
            )

    @property
    def subbreed_id(self) -> str | None:
        return self.definition.subbreed

    @property
    def type_name(self) -> str:
        if sb := self.subbreed:
            return sb.display_name()
        return super().type_name

    @property
    def feature_list_name(self) -> str:
        if sb := self.subbreed:
            name = f"{super().feature_list_name} [{sb.display_name()}]"
        else:
            name = f"{super().feature_list_name}"
        if self.paid_ranks:
            name = f"{name} ({self.award_bp} BP)"
        return name

    @property
    def subbreed(self) -> feature_controller.FeatureController | None:
        if sbi := self.subbreed_id:
            return self.character.controller(sbi)
        return None

    def can_afford(self, value: int = 1) -> Decision:
        if sbi := self.subbreed_id:
            if not self.parent.is_primary:
                return Decision(
                    success=False, reason="Only primary breed can select subbreeds"
                )
            if self.parent.subbreed_id is None:
                return Decision.OK
            if self.parent.subbreed_id != sbi:
                return Decision(success=False, reason="Subbreed mismatch")
        return Decision.OK

    @cached_property
    def award_options(self) -> dict[str, int] | None:
        if not isinstance(self.definition.award, dict):
            return None
        award_dict: dict[str, int] = {}
        flags_to_eval: dict[str, int] = {}
        for option, value in self.definition.award.items():
            if not option.startswith("$"):
                award_dict[option] = value
            else:
                flags_to_eval[option[1:]] = value
        for flag, value in flags_to_eval.items():
            for f in utils.maybe_iter(self.character.flags.get(flag)):
                if f is None:
                    continue
                if not isinstance(f, str):
                    f = str(f)
                # Negative flag. Remove from awards *if* it has the matching value.
                if f.startswith("-"):
                    f = f[1:]
                    if f in award_dict and award_dict[f] == value:
                        del award_dict[f]
                else:
                    award_dict[f] = value
        return award_dict

    @property
    def award_bp(self):
        """BP awarded for having the flaw.

        Zero if no BP was awarded for the flaw.
        """
        if self.model.plot_free:
            return 0
        return self._award_value

    @property
    def _award_value(self) -> int:
        """Amount of BP that would be awarded, assuming this challenge was taken at character creation."""
        award: int = 0
        if isinstance(self.definition.award, int):
            award = self.definition.award
        else:
            award = self.award_options.get(self.option, 0)
        # The award value can be modified if other features are present.
        if self.definition.award_mods:
            for flaw, mod in self.definition.award_mods.items():
                if self.character.get(flaw) > 0:
                    award += mod
        return max(award * self.paid_ranks, 0)

    def purchase_cost_string(self, ranks: int = 1, cost: int | None = None) -> str:
        match self.definition.award:
            case int():
                return f"+{self.definition.award} BP"
            case dict():
                # The award varies based on a table of options. Determine the spread and use that.
                values = set(self.award_options.values())
                min_v = min(values)
                max_v = max(values)
                if min_v == max_v:
                    return f"+{min_v} BP"
                return f"+{min_v}-{max_v} BP"
            case _:
                return "+? BP"

    @property
    def explain(self) -> list[str]:
        reasons = super().explain

        if sb := self.subbreed:
            reasons.append(
                f"Part of the [{sb.display_name()}](../{sb.full_id}) subbreed"
            )

        if self.award_bp:
            reasons.append(f"You receive {self.award_bp} BP from this flaw.")
        return reasons
