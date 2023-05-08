from __future__ import annotations

from django import forms

from camp.engine.rules.base_engine import BaseFeatureController


class FeatureForm(forms.Form):
    _controller: BaseFeatureController

    def __init__(self, controller: BaseFeatureController, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._make_ranks_field(controller)
        self._make_option_field(controller)

    def _make_ranks_field(self, c: BaseFeatureController) -> forms.Field:
        available = c.available_ranks
        if c.option_def and not c.option:
            current = 0
        else:
            current = c.value
        choices = []
        if available == 1 and c.definition.ranks == 1:
            # The only thing that can happen here is purchasing 1 rank, so don't
            # bother with a choice field.
            return
        if available > 0 and c.definition.ranks != 1:
            next_value = c.next_value
            if c.currency:
                choices.extend(
                    (i, f"{i} ({c.purchase_cost_string(i)})")
                    for i in range(next_value, next_value + available)
                )
            else:
                choices = [(i, i) for i in range(next_value, next_value + available)]
        if c.can_decrease():
            choices = (
                [(i, i) for i in range(c.min_value, current)]
                + [(current, f"{current} (Current)")]
                + choices
            )
        if choices:
            self.fields["ranks"] = forms.ChoiceField(
                choices=choices,
                label=f"New {c.rank_name_labels[0].title()}",
            )

    def _make_option_field(self, c: BaseFeatureController):
        if not c.option and c.option_def:
            available = c.available_options
            if c.option_def.freeform:
                if c.option_def.freeform:
                    if available:
                        widget = DatalistTextInput(available)
                        help = f"This {c.type_name.lower()} takes a custom option. Enter it here. Suggestions: {', '.join(available)}."
                    else:
                        widget = forms.TextInput
                        help = f"This {c.type_name.lower()} takes a custom option. Enter it here."
                    self.fields["option"] = forms.CharField(
                        max_length=100,
                        label="Option",
                        widget=widget,
                        help_text=help,
                    )
            elif available:
                # If the option has both choices *and* freeform. The choices are basically
                # just a suggestion, so we'll let the user enter whatever they want and provide a
                # datalist.
                self.fields["option"] = forms.ChoiceField(
                    choices=[(a, a) for a in available],
                    label="Options",
                    help_text="Select an option. If you don't see the option you want, ask plot staff.",
                )


class DatalistTextInput(forms.TextInput):
    template_name = "character/widgets/datalist_text_input.html"

    def __init__(self, datalist: list[str], attrs: dict | None = None):
        self.datalist = sorted(datalist)
        super().__init__(attrs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs["list"] = self.datalist
        return super().render(name, value, attrs, renderer)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["datalist"] = self.datalist
        datalist_id = name + "_datalist"
        context["widget"]["attrs"]["list"] = datalist_id
        return context
