import re

from django import forms
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from camp.accounts.models import User
from camp.character.models import Character
from camp.engine.rules.base_models import FlagValue
from camp.engine.rules.tempest.records import AwardCategory
from camp.engine.rules.tempest.records import AwardRecord
from camp.game.models.event_models import _XP_PER_HALFDAY

from . import models
from .fields import DateField
from .fields import DateTimeField
from .fields import DefaultModelChoiceField

FLAG_SEP = re.compile(r"[ ,;\n\t\r]+")


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
        char_query = self.instance.user.characters.filter(discarded_date=None)
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


CATEGORY_CHOICE_DICT = {
    AwardCategory.EVENT: "Event Credit",
    AwardCategory.PLOT: "Plot Awards",
    # TODO: Support other categories.
}

CATEGORY_CHOICES = [
    (category, label) for category, label in CATEGORY_CHOICE_DICT.items()
]

# Forms for the award grant flow.


class AwardPlayerStep(forms.Form):
    player = forms.ModelChoiceField(
        queryset=User.objects,
        to_field_name="username",
        required=False,
        help_text="Player to receive the award.",
    )
    email = forms.EmailField(
        required=False,
        help_text="Or, enter an email address. This will work even if the player hasn't created an account yet; the system will remember the award until they verify their email and claim the award.",
    )

    award_category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        help_text="What type of award?",
        required=True,
        widget=forms.RadioSelect,
    )
    step = forms.IntegerField(initial=1, widget=forms.HiddenInput())

    def clean(self):
        data = super().clean()
        player = data.get("player")
        email = data.get("email")
        if player and email:
            del data["email"]
        if (not player) and (not email):
            raise forms.ValidationError("Player or Email must be specified")
        return data


class _AwardStepTwo(AwardPlayerStep):
    """Convert a few fields to hidden, and add a character selector."""

    player = forms.ModelChoiceField(
        queryset=User.objects,
        to_field_name="username",
        required=False,
        widget=forms.HiddenInput,
    )
    email = forms.EmailField(required=False, widget=forms.HiddenInput)
    award_category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.HiddenInput,
        required=True,
    )
    character = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="[Not bound to a character]",
        help_text="Select a character. If not bound, this will not be applied immediately, and the player will choose what character to apply it to (if needed).",
    )
    description = forms.CharField(
        required=False, help_text="(Optional) Enter a description for this award"
    )
    step = forms.IntegerField(initial=2, widget=forms.HiddenInput())

    def __init__(self, *args, character_query: QuerySet[Character] | None, **kwargs):
        super().__init__(*args, **kwargs)
        if character_query is None:
            del self.fields["character"]
        else:
            self.fields["character"].queryset = character_query

    def create_award(self, request) -> models.Award:
        raise NotImplementedError


class AwardEventStep(_AwardStepTwo):
    attendance = forms.ChoiceField(
        choices=[(None, "Neither"), ("pc", "PC"), ("npc", "NPC/Staff")],
        help_text="What type of event credit?",
        required=False,
        widget=forms.RadioSelect,
    )
    event = forms.ModelChoiceField(
        queryset=None,  # Fill this based on the user and campaign.
        required=True,
    )
    event_xp = forms.IntegerField(
        label="Event XP",
        min_value=0,
        help_text="Amount of Event XP to grant. A weekend event usually grants 8.",
        initial=8,
        required=True,
    )
    event_cp = forms.BooleanField(
        label="Event CP",
        help_text="Grants 1 CP for the event.",
        initial=True,
        required=False,
    )

    def __init__(self, *args, event_query: QuerySet[models.Event], **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event"].queryset = event_query

    def create_award(self, campaign, request) -> models.Award:
        player = self.cleaned_data.get("player")
        email = self.cleaned_data.get("email")
        character = self.cleaned_data.get("character")
        description = self.cleaned_data.get("description")
        event: models.Event = self.cleaned_data["event"]
        event_xp: int = self.cleaned_data["event_xp"]
        event_cp: int = 1 if self.cleaned_data["event_cp"] else 0
        attendance: str | None = self.cleaned_data.get("attendance")
        awarded_by = request.user
        chapter = event.chapter

        # TODO: Make this a campaign setting?
        event_max_xp = int(event.logistics_periods * _XP_PER_HALFDAY)
        event_xp = max(min(event_max_xp, event_xp), 0)

        record = AwardRecord(
            date=event.event_end_date.date(),
            source_id=event.id,
            category=AwardCategory.EVENT,
            description=description,
            character=character.id if character else None,
            event_xp=event_xp,
            event_cp=event_cp,
            event_played=(attendance == "pc"),
            event_staffed=(attendance == "npc"),
        )

        with transaction.atomic():
            award: models.Award = models.Award.objects.create(
                campaign=campaign,
                player=player,
                character=character,
                email=email,
                chapter=chapter,
                event=event,
                awarded_by=awarded_by,
                award_data=record.model_dump(mode="json"),
            )

            if player and character:
                award.apply()
        return award

    def clean(self):
        data = super().clean()
        player = data.get("player")
        event = data["event"]
        if player:
            player_data = models.PlayerCampaignData.retrieve_model(
                player, event.campaign, update=False
            )
            record = player_data.record
            for award in record.awards:
                if (
                    award.category == AwardCategory.EVENT
                    and award.source_id
                    and str(award.source_id) == str(event.id)
                ):
                    self.add_error(
                        "event",
                        forms.ValidationError(
                            f"{player} already has credit for {event}",
                            code="ineligible",
                        ),
                    )
        return data


class AwardPlotStep(_AwardStepTwo):
    backdate = DateField(
        required=False,
        label="Backdate To",
        help_text="To backdate this award, enter a date. Otherwise, it is applied as of now.",
    )
    backstory = forms.BooleanField(
        required=False,
        help_text="Grants the character an extra +2 CP for an approved backstory",
    )
    bonus_cp = forms.IntegerField(
        min_value=0,
        max_value=10,
        initial=0,
        required=False,
        help_text="Grant Bonus CP. This is a per-player value. Capped at 3 per Season",
    )
    player_flags = forms.CharField(
        required=False,
        help_text="Enter one or more player-level flag names for special unlocks. These are usually just the name of the feature being unlocked, with any spaces replaced with - dashes",
    )
    character_flags = forms.CharField(
        required=False,
        help_text="Enter one or more character-level flag names for special unlocks. These are usually just the name of the feature being unlocked, with any spaces replaced with - dashes",
    )
    # Grants are not implemented yet.
    # grants = forms.CharField(
    #     required=False,
    #     help_text="Enter one or more character bonus grants to add for free. For example, to grant 3 extra life points, enter lp:3",
    # )

    def create_award(self, campaign, request) -> models.Award:
        player = self.cleaned_data.get("player")
        email = self.cleaned_data.get("email")
        character = self.cleaned_data.get("character")
        description = self.cleaned_data.get("description")
        grant_backstory = self.cleaned_data["backstory"]
        bonus_cp = self.cleaned_data["bonus_cp"]
        raw_player_flag = self.cleaned_data.get("player_flags")
        raw_character_flags = self.cleaned_data.get("character_flags")
        raw_grants = self.cleaned_data.get("grants")
        awarded_by = request.user
        player_flags = None
        character_flags = None
        grants = None

        backdate = self.cleaned_data.get("backdate")
        if not backdate:
            backdate = timezone.now().date()

        if raw_player_flag:
            player_flags: dict[str, FlagValue] = {}
            for flag in FLAG_SEP.split(raw_player_flag):
                _add_flag(player_flags, flag)
        if raw_character_flags:
            character_flags: dict[str, FlagValue] = {}
            for flag in FLAG_SEP.split(raw_character_flags):
                _add_flag(character_flags, flag)

        if raw_grants:
            grants = FLAG_SEP.split(raw_grants)

        record = AwardRecord(
            date=backdate,
            category=AwardCategory.PLOT,
            description=description,
            character=character.id if character else None,
            bonus_cp=bonus_cp,
            # False means "revoke backstory approval", which we
            # won't use here at present (prefer to delete the award)
            backstory_approved=True if grant_backstory else None,
            player_flags=player_flags,
            character_flags=character_flags,
            character_grants=grants,
        )

        with transaction.atomic():
            award: models.Award = models.Award.objects.create(
                campaign=campaign,
                player=player,
                character=character,
                email=email,
                awarded_by=awarded_by,
                award_data=record.model_dump(mode="json"),
            )

            if player and character:
                award.apply()
        return award


def _add_flag(flags: dict[str, FlagValue], flag: str):
    if "=" in flag:
        flag, value = flag.split("=", maxsplit=1)
        if not value:
            value = None
        else:
            # Check if it's a numeric type...
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
    else:
        value = True

    if flag.startswith("-") or flag.startswith("!"):
        value = not value
        flag = flag[1:]

    flags[flag] = value
