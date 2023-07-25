from __future__ import annotations

from django import forms

from camp.engine.rules.base_engine import ChoiceController
from camp.engine.rules.tempest.controllers.class_controller import ClassController
from camp.engine.rules.tempest.controllers.feature_controller import FeatureController


class FeatureForm(forms.Form):
    _controller: FeatureController
    button_label: str = "Purchase"
    button_level: str = "primary"

    def __init__(self, controller: FeatureController, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._controller = controller
        self._make_ranks_field(controller)
        self._make_option_field(controller)

    @property
    def show_remove_button(self) -> bool:
        """Whether to show the remove button.

        At present, the remove button is only shown if this is a single-rank feature.
        Multi-rank features are removed by setting the rank to 0 in the rank chooser.
        """
        c = self._controller
        return c.value == 1 and c.definition.ranks == 1 and c.can_decrease()

    def _make_ranks_field(self, c: FeatureController) -> forms.Field:
        # If the feature only needs a remove button, don't bother with a ranks field.
        if self.show_remove_button:
            return

        available = c.available_ranks
        if c.option_def and not c.option:
            current = 0
        else:
            current = c.value
        choices = []
        if available == 1 and c.definition.ranks == 1:
            # The only thing that can happen here is purchasing 1 rank, so don't
            # bother with a choice field.
            if c.unused_bonus > 0:
                self.button_label = "Get!"
                self.button_level = "success"
            return
        if available > 0 and c.definition.ranks != 1:
            next_value = c.next_value
            if c.currency:
                choices.extend(
                    (i, f"{i} ({c.purchase_cost_string(i - current)})")
                    for i in range(next_value, current + available + 1)
                )
            else:
                choices = [(i, i) for i in range(next_value, current + available + 1)]
        if c.can_decrease():
            choices = (
                [(i, i) for i in range(c.min_value, current)]
                + [(current, f"{current} (Current)")]
                + choices
            )
            self.button_label = "Update"
        # Special case: Your starting class level can be 0 (if you're removing it) or 2,
        # but it can never be 1. I don't think there are any other cases where a feature has
        # a weird discontinuity, so I'm not going to try to generalize this for now.
        if isinstance(c, ClassController) and c.is_starting:
            if (1, 1) in choices:
                choices.remove((1, 1))
        if choices:
            self.fields["ranks"] = forms.ChoiceField(
                choices=choices,
                label=f"New {c.rank_name_labels[0].title()}",
            )

    def _make_option_field(self, c: FeatureController):
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


class ChoiceForm(forms.Form):
    _choice: str
    controller: ChoiceController
    taken: dict[str, str]
    removable: set[str]

    @property
    def id(self) -> str:
        return self.controller.id

    def __init__(self, controller: ChoiceController, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.controller = controller
        self.available = controller.available_choices()
        self.taken = controller.taken_choices()
        self.removable = controller.removeable_choices()
        self._make_choice_field()

    def _make_choice_field(self):
        if self.available:
            choices = [(k, v) for (k, v) in self.available.items()]
            self.fields["selection"] = forms.ChoiceField(
                choices=choices,
                label="Available Choices",
                help_text="Make a selection.",
            )
