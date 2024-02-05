from django import forms

from .fields import DateTimeField
from .fields import DefaultModelChoiceField
from .models import event_models as models


class EventCreateForm(forms.ModelForm):
    class Meta:
        model = models.Event
        fields = [
            "name",
            "type",
            "description",
            "location",
            "payment_details",
            "details_template",
            "campaign",
            "event_start_date",
            "event_end_date",
            "registration_open",
            "registration_deadline",
            "logistics_periods",
            "daygame_logistics_periods",
            "tenting_allowed",
            "cabin_allowed",
        ]
        field_classes = {
            "chapter": DefaultModelChoiceField,
            "campaign": DefaultModelChoiceField,
            "event_start_date": DateTimeField,
            "event_end_date": DateTimeField,
            "registration_open": DateTimeField,
            "registration_deadline": DateTimeField,
        }


class EventUpdateForm(forms.ModelForm):
    class Meta:
        model = models.Event
        fields = [
            "name",
            "type",
            "description",
            "location",
            "payment_details",
            "details_template",
            "event_start_date",
            "event_end_date",
            "registration_open",
            "registration_deadline",
            "logistics_periods",
            "daygame_logistics_periods",
            "logistics_year",
            "logistics_month",
            "tenting_allowed",
            "cabin_allowed",
        ]
        field_classes = {
            "event_start_date": DateTimeField,
            "event_end_date": DateTimeField,
            "registration_open": DateTimeField,
            "registration_deadline": DateTimeField,
        }


class RegisterForm(forms.ModelForm):
    is_npc = forms.BooleanField(
        label="Registration Type",
        required=False,
        widget=forms.RadioSelect(
            choices=[
                (False, "Register as a Player (PC)"),
                (True, "Register as a Volunteer (NPC)"),
            ]
        ),
    )

    character = DefaultModelChoiceField(
        help_text=(
            "Select a character to play. "
            "If registering as an NPC, this character receives credit for the event."
        ),
        queryset=None,
    )

    lodging = forms.ChoiceField(
        widget=forms.RadioSelect,
        help_text=models.EventRegistration.lodging.field.help_text,
    )
    lodging_group = forms.CharField(
        widget=forms.TextInput,
        help_text=models.EventRegistration.lodging_group.field.help_text,
        required=False,
    )

    details = forms.CharField(
        widget=forms.Textarea,
        help_text="Enter any other details required.",
        required=False,
    )

    def __init__(self, *args, allow_payment=False, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up the character field. It should only show characters belonging
        # to the registering player. It will behave a little differently
        # if you have no characters (we'll create a blank character upon
        # successful registration).
        char_query = self.instance.user.characters
        # If this is not a freeplay event, only allow characters from
        # the event's campaign.
        event: models.Event = self.instance.event
        if event.campaign:
            char_query = char_query.filter(campaign=event.campaign)
        char_field: DefaultModelChoiceField = self.fields["character"]
        char_field.queryset = char_query
        if char_query.count() == 0:
            char_field.help_text = "You don't have a character in this campaign. We'll create a blank character sheet when you register. If you're NPCing, you can ignore this."
            char_field.required = False
            char_field.disabled = True
            char_field.empty_label = "[No Characters]"
        if event.daygame_logistics_periods <= 0:
            del self.fields["attendance"]

        # Lodging form data. Default lodging is whatever is "best" (Cabin if allowed, else tenting if allowed, else none)
        self.fields["lodging"].choices = lodging_choices = event.lodging_choices
        self.initial["lodging"] = lodging_choices[-1][0]

        # Payment fields are only available to logistics.
        if not allow_payment:
            del self.fields["payment_complete"]
            del self.fields["payment_note"]

    class Meta:
        model = models.EventRegistration
        fields = [
            "is_npc",
            "attendance",
            "lodging",
            "lodging_group",
            "character",
            "details",
            "payment_complete",
            "payment_note",
        ]
