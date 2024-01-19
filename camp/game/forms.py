from django import forms

from . import models
from .fields import DateField
from .fields import DateTimeField
from .fields import DefaultModelChoiceField


class EventCreateForm(forms.ModelForm):
    class Meta:
        model = models.Event
        fields = [
            "name",
            "description",
            "location",
            "details_template",
            "campaign",
            "event_start_date",
            "event_end_date",
            "registration_open",
            "registration_deadline",
            "logistics_periods",
        ]
        field_classes = {
            "chapter": DefaultModelChoiceField,
            "campaign": DefaultModelChoiceField,
            "event_start_date": DateField,
            "event_end_date": DateField,
            "registration_open": DateTimeField,
            "registration_deadline": DateTimeField,
        }


class EventUpdateForm(forms.ModelForm):
    class Meta:
        model = models.Event
        fields = [
            "name",
            "description",
            "location",
            "details_template",
            "event_start_date",
            "event_end_date",
            "registration_open",
            "registration_deadline",
            "logistics_periods",
            "logistics_year",
            "logistics_month",
        ]
        field_classes = {
            "event_start_date": DateField,
            "event_end_date": DateField,
            "registration_open": DateTimeField,
            "registration_deadline": DateTimeField,
        }


class RegisterForm(forms.ModelForm):
    is_npc = forms.BooleanField(
        label="Register as an NPC",
        required=False,
        help_text="Volunteer for this event instead of registering as a player?",
    )
    character = DefaultModelChoiceField(
        help_text=(
            "Select a character to play. "
            "If registering as an NPC, this character receives credit for the event."
        ),
        queryset=None,
    )
    details = forms.CharField(
        widget=forms.Textarea, help_text="Enter any other details required."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up the character field. It should only show characters belonging
        # to the registering player. It will behave a little differently
        # if you have no characters (we'll create a blank character upon
        # successful registration).
        char_query = self.instance.user.characters
        # If this is not a freeplay event, only allow characters from
        # the event's campaign.
        if self.instance.event.campaign:
            char_query = char_query.filter(campaign=self.instance.event.campaign)
        char_field: DefaultModelChoiceField = self.fields["character"]
        char_field.queryset = char_query
        if char_query.count() == 0:
            char_field.help_text = "You don't have a character in this campaign. We'll create a blank character sheet when you register. If you're NPCing, you can ignore this."
            char_field.required = False
            char_field.disabled = True
            char_field.empty_label = "[No Characters]"

    class Meta:
        model = models.EventRegistration
        fields = ["is_npc", "character", "details"]
