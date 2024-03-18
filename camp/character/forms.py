from __future__ import annotations

import re

from django import forms

from camp.character.models import Character
from camp.engine.rules.base_engine import ChoiceController
from camp.engine.rules.tempest.controllers.class_controller import ClassController
from camp.engine.rules.tempest.controllers.feature_controller import FeatureController
from camp.game.models import Campaign

OPEN_CAMPAIGNS = Campaign.objects.filter(is_open=True).order_by("name")

ALLOWED_FREEFORM_PATTERN = r"^[\w&.․()!?：:;,[\]|%/\\ -]+$"
ALLOWED_FREEFORM = re.compile(ALLOWED_FREEFORM_PATTERN)


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
        return c.value == 1 and c.max_ranks == 1 and c.can_decrease()

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
        if c.unused_bonus > 0 and c.max_ranks == 1:
            self.button_label = "Get!"
            self.button_level = "success"
            return
        if available > 0 and c.max_ranks != 1:
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

    def selected_option(self) -> str | None:
        if "option" in self.cleaned_data and self.cleaned_data["option"] != "__other__":
            return self.cleaned_data["option"]
        if "option_freeform" in self.cleaned_data:
            return self.cleaned_data["option_freeform"]
        return None

    def _make_option_field(self, c: FeatureController):
        if not c.option and (option_def := c.option_def):
            available = c.available_options
            if available:
                options = [(a, c.describe_option(a)) for a in available]
                help_text = "Select an option."
                if option_def.freeform:
                    options.append(("__other__", "Other"))
                    help_text = "Select an option, or Other to enter a custom option."
                self.fields["option"] = forms.ChoiceField(
                    widget=forms.RadioSelect,
                    choices=options,
                    label="Options",
                    help_text=help_text,
                )
            if option_def.freeform:
                self.fields["option_freeform"] = freeform = forms.CharField(
                    max_length=100,
                    label="Custom Option",
                    required=not (available),
                    help_text=f"This {c.type_name.lower()} takes a custom option. Enter it here.",
                )
                freeform.widget.attrs.update({"pattern": ALLOWED_FREEFORM_PATTERN})

    def clean_option_freeform(self) -> str | None:
        if value := self.cleaned_data.get("option_freeform"):
            value = value.replace(".", "․")
            value = value.replace(":", "：")
            if not ALLOWED_FREEFORM.match(value):
                raise forms.ValidationError(
                    f"{value} is not a valid option (try removing some special characters)"
                )
            return value
        return None


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


class NewCharacterForm(forms.ModelForm):
    campaign = forms.ModelChoiceField(
        queryset=OPEN_CAMPAIGNS,
        empty_label="Freeplay (build experiments, not playable)",
        help_text="Will this be a campaign character, or a freeplay character? Freeplay characters can be edited freely and are useful for build planning, but can't be used at events.",
        widget=forms.RadioSelect,
        required=False,
        blank=True,
    )

    class Meta:
        model = Character
        fields = ["name", "campaign"]
