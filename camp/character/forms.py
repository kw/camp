from __future__ import annotations

from django import forms

from camp.engine.rules.base_engine import BaseFeatureController


def purchase_form(controller: BaseFeatureController) -> forms.Form:
    ...


# How do we create forms for each feature? We can either create a form metaclass
# that we can generate a class for each feature from, or we can use a single form
# class that generates its fields attribute dynamically from the feature definition.
# The metaclass approach seems overkill here, so we'll go with the latter for now.


class FeatureForm(forms.Form):
    _controller: BaseFeatureController

    def __init__(self, controller: BaseFeatureController, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._controller = controller
        self._make_ranks_field()
        if not controller.option and controller.option_def:
            # Definition specifies option, but this controller doesn't have one.
            # TODO: If an option list is provided, use it.
            self.fields["option"] = forms.CharField(
                max_length=100,
            )

    def _make_ranks_field(self) -> forms.Field:
        available = self._controller.available_ranks
        current = self._controller.value
        if available > 0 and self._controller.definition.ranks != 1:
            if self._controller.currency:
                choices = [
                    (i, f"{current + i} ({self._controller.purchase_cost_string(i)})")
                    for i in range(1, available + 1)
                ]
            else:
                choices = [(i, current + i) for i in range(1, available + 1)]
            rank_name = self._controller.rank_name_labels[0].title()
            self.fields["ranks"] = forms.ChoiceField(
                choices=choices,
                label=f"New {rank_name}",
            )
