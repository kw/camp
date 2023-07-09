from camp.engine.rules.base_models import Discount

from . import choice_controller


class PatronChoice(choice_controller.BaseFeatureChoice):
    def available_choices(self) -> dict[str, str]:
        # Already taken too many?
        if self.choices_remaining <= 0:
            return {}

        feats = self._matching_features()
        feats -= set(self.taken_choices().keys())

        choices = {}
        for expr in sorted(feats):
            feat = self._feature.character.feature_controller(expr)
            short = feat.short_description
            name = getattr(feat, "formal_name", feat.display_name())
            choices[expr] = f"{name}: {short}" if short else name
        return choices

    def update_propagation(
        self, grants: dict[str, int], discounts: dict[str, list[Discount]]
    ) -> None:
        for choice in self.taken_choices():
            if self._feature.model.plot_suppressed:
                # TODO(#38): Propagate suppression to chosen features.
                continue
            if choice not in discounts:
                discounts[choice] = []
            discounts[choice].append(Discount(discount=1, ranks=1))
