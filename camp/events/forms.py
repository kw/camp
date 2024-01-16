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
