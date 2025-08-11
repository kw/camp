from __future__ import annotations

import datetime
import logging
import uuid
from decimal import Decimal
from typing import TypeAlias

from django.contrib.auth import get_user_model
from django.db import models
from django.db import transaction
from django.db.models import F
from django.db.models import Q
from django.db.models import QuerySet
from django.urls import reverse
from django.utils import timezone
from rules.contrib.models import RulesModel

import camp.accounts.models as account_models
from camp.engine.rules.tempest import campaign
from camp.engine.rules.tempest.records import AwardCategory
from camp.engine.rules.tempest.records import AwardRecord

from . import game_models

User: TypeAlias = get_user_model()  # type: ignore


# TODO: Make this a campaign setting
_XP_PER_HALFDAY = Decimal(2)


class Month(models.IntegerChoices):
    JAN = 1, "Jan"
    FEB = 2, "Feb"
    MAR = 3, "Mar"
    APR = 4, "Apr"
    MAY = 5, "May"
    JUN = 6, "Jun"
    JUL = 7, "Jul"
    AUG = 8, "Aug"
    SEPT = 9, "Sept"
    OCT = 10, "Oct"
    NOV = 11, "Nov"
    DEC = 12, "Dec"


class Attendance(models.IntegerChoices):
    FULL = 0, "Full Game"
    DAY = 1, "Day Game"
    # TODO: More granularity


class EventType(models.IntegerChoices):
    EVENT = 0, "Standard"
    MOD = 1, "Module"
    TAVERN = 2, "Tavern"


class Lodging(models.IntegerChoices):
    NONE = 0, "No Lodging"
    TENT = 1, "Tent Camping"
    CABIN = 2, "Cabin"


class Event(RulesModel):
    name: str = models.CharField(max_length=100, blank=True)
    type: int = models.IntegerField(default=EventType.EVENT, choices=EventType.choices)
    description: str = models.TextField(blank=True)
    location: str = models.TextField(
        blank=True,
        default="",
        help_text="Physical address, maybe with a map link. Markdown enabled.",
    )
    payment_details: str = models.TextField(
        blank=True,
        default="",
        help_text="Payment information. Markdown enabled. Recommend linking to payment pages.",
    )
    details_template: str = models.TextField(
        blank=True,
        help_text="This text will be pre-filled into the registration form. A quick way to include questions that are not part of the default form.",
    )

    chapter: game_models.Chapter = models.ForeignKey(
        game_models.Chapter, on_delete=models.PROTECT, related_name="events"
    )
    campaign: game_models.Campaign = models.ForeignKey(
        game_models.Campaign, on_delete=models.PROTECT, related_name="events"
    )
    creator: User = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    canceled_date = models.DateTimeField(blank=True, null=True)

    registration_open = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When should the Register button be shown, in the chapter's local timezone? Leave blank to never open (until you set it).",
    )
    registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When should the Register button go away, in the chapter's local timezone? Leave blank to open until end-of-event.",
    )
    event_start_date = models.DateTimeField()
    event_end_date = models.DateTimeField()

    tenting_allowed = models.BooleanField(
        default=True, help_text="Allow players to register for tent-based lodging."
    )
    cabin_allowed = models.BooleanField(
        default=True, help_text="Allow players to register for cabin lodging."
    )

    logistics_periods = models.DecimalField(
        # TODO: Instead of a global static default, make this a campaign setting,
        # or make the campaign engine guess based on the selected date range.
        max_digits=4,
        decimal_places=2,
        default=Decimal(4),
        help_text="How many half days?",
    )
    daygame_logistics_periods = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal(2),
        help_text="How many half-days for a daygamer? Set to zero to disallow daygaming. Must be less than the normal reward.",
    )
    completed = models.BooleanField(default=False)

    registrations: QuerySet[EventRegistration]

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = str(self)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.name:
            effective_name = self.name
        else:
            effective_name = f"{self.chapter} {self.logistics_month_label}"
        if self.is_canceled:
            effective_name = f"{effective_name} [CANCELED]"
        return effective_name

    def get_absolute_url(self):
        return reverse("event-detail", kwargs={"pk": self.pk})

    def registration_window_open(self):
        if not self.registration_open:
            # A game with no registration open date may be historical or far enough in the future
            # that the logi doesn't want to set it yet. Always false.
            return False
        now = timezone.now()
        if now < self.registration_open:
            return False
        if self.registration_deadline and now > self.registration_deadline:
            return False
        # If no registration deadline was specified, we don't allow registration
        # past the end of the event.
        if not self.registration_deadline and now > self.event_end_date:
            return False
        return True

    def event_in_progress(self):
        return self.event_start_date <= timezone.now() <= self.event_end_date

    @property
    def logistics_month_label(self) -> str:
        return self.event_end_date.strftime("%b %Y")

    @property
    def record(self) -> campaign.EventRecord:
        return campaign.EventRecord(
            chapter=self.chapter.slug,
            date=self.event_end_date.date(),
            xp_value=int(self.logistics_periods * _XP_PER_HALFDAY),
            cp_value=1 if self.logistics_periods else 0,
        )

    @property
    def is_canceled(self):
        return bool(self.canceled_date)

    @property
    def is_old(self):
        """An event is _old_ if it is both complete/canceled and in the past."""
        return self.event_end_date < timezone.now() and (
            self.completed or self.is_canceled
        )

    @property
    def lodging_choices(self):
        choices = [(Lodging.NONE.value, Lodging.NONE.label)]
        if self.tenting_allowed:
            choices.append((Lodging.TENT.value, Lodging.TENT.label))
        if self.cabin_allowed:
            choices.append((Lodging.CABIN.value, Lodging.CABIN.label))
        return choices

    def can_complete(self) -> tuple[bool, str]:
        """Determine if the event can currently be marked 'complete'.

        Returns: (completable: bool, reason: str)
        completable: If true, it's safe to perform the completion task.
        reason: Otherwise, the reason for the failure is given here.
        """
        if self.completed:
            return False, "Already marked complete."

        # Depending on the logistics team, someone might want to mark attendance during the game,
        # possibly even as soon as during checkin. But, under no circumstances should a game be
        # marked complete before it has even started.
        if self.event_start_date > timezone.now():
            return False, "Event hasn't even started yet."

        if self.is_canceled:
            return False, "A canceled event can't be marked complete."

        previous_date = self.campaign.record.last_event_date
        if previous_date > self.record.date:
            return False, (
                "Event could not be integrated into the campaign model. "
                f"It occurred prior to the last event ({previous_date})."
            )

        return True, "Event can be completed."

    @transaction.atomic
    def mark_complete(self):
        """Updates the campaign's progress, then marks the event as complete.

        This is an atomic operation. The model will be saved with complete=True
        if this succeeds, which will have occurred unless an exception is raised.
        """
        can, reason = self.can_complete()
        if not can:
            raise ValueError(reason)

        campaign = self.campaign
        campaign_model = campaign.record
        event_model = self.record
        previous_date = campaign_model.last_event_date
        if previous_date > event_model.date:
            raise ValueError(
                "Event could not be integrated into the campaign model. "
                f"It occurred prior to the last event ({previous_date})."
            )
        campaign.record = campaign_model.add_events([event_model])
        self.completed = True
        campaign.save()
        self.save()

    def get_registration(self, user: User) -> EventRegistration | None:
        """Returns the event registration corresponding to this user, if it exists.

        If the user has not registered for this event, returns None.
        """
        if user.is_anonymous:
            return None
        try:
            return EventRegistration.objects.get(event=self, user=user)
        except EventRegistration.DoesNotExist:
            return None

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="end_date_gte_start",
                violation_error_message="End date must not be before start date.",
                check=Q(event_end_date__gte=F("event_start_date")),
            ),
            models.CheckConstraint(
                name="logistics_periods_nonneg",
                violation_error_message="Number of logistics periods must be non-negative.",
                check=Q(logistics_periods__gte=Decimal(0)),
            ),
            models.CheckConstraint(
                name="daygame_reward",
                violation_error_message="Daygame logistics reward must not be greater than the normal one.",
                check=Q(daygame_logistics_periods__lte=F("logistics_periods")),
            ),
            models.CheckConstraint(
                name="daygame_periods_nonneg",
                violation_error_message="Number of daygame logistics periods must be non-negative.",
                check=Q(daygame_logistics_periods__gte=Decimal(0)),
            ),
        ]

        indexes = [
            models.Index(
                fields=["campaign", "chapter"],
                name="game-campaign-idx",
            ),
        ]

        rules_permissions = {
            "view": game_models.always_allow,
            "add": game_models.can_manage_events,
            "change": game_models.can_manage_events,
            "delete": game_models.can_manage_events,
        }


class EventRegistration(RulesModel):
    # You can't delete an event once people start signing up for it.
    # You can still cancel the event, but the registrations persist in case
    # there is payment or other information attached.
    event: Event = models.ForeignKey(
        Event,
        related_name="registrations",
        on_delete=models.PROTECT,
    )
    # But if a user is deleted, clear them out.
    user: User = models.ForeignKey(
        User, related_name="event_registrations", on_delete=models.CASCADE
    )
    is_npc: bool = models.BooleanField(default=False)
    attendance: int = models.IntegerField(
        default=Attendance.FULL,
        choices=Attendance.choices,
        help_text="How much of the event are you registering for?",
    )
    lodging: int = models.IntegerField(
        choices=Lodging.choices,
        help_text="What lodgings do you need? Daygamers, pick No Lodging. NPCs typically get a cabin.",
    )
    lodging_group: str = models.TextField(
        blank=True,
        help_text=(
            "If you wish to stay with a group or individual, indicate that here. "
            "For any other lodging concerns, use the Other Details field."
        ),
    )
    details: str = models.TextField(blank=True, verbose_name="Other Details")

    character = models.ForeignKey(
        "character.Character",
        related_name="event_registrations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # By default we'll take the primary character sheet.
    sheet = models.ForeignKey(
        "character.Sheet",
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
    )

    registered_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    # If the user (or staff) want to cancel a registration, record when it happened.
    canceled_date = models.DateTimeField(null=True, blank=True)

    # Fields for post-game record keeping.
    attended = models.BooleanField(default=False)
    attended_periods = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    award_applied_date = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Timestamp when this award was applied to the character record, if it was applied.",
    )
    award_applied_by = models.ForeignKey(
        User,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )

    # Fields for logi to fill in regarding payment.
    # Later, a payment system might handle this.
    payment_complete: bool = models.BooleanField(default=False)
    payment_note: str = models.TextField(blank=True, default="")

    def award_record(
        self, logistics_periods: int | Decimal | None = None
    ) -> AwardRecord:
        """Generates an award record suitable for this event registration.

        Arguments:
            logistics_periods: If specified (and positive), the number of logistics
                periods (half-days, in Tempest) to base rewards on. If not specified,
                this defaults to whatever the `attendance` field indicates.
        """
        # TODO: Once we're tracking SP, include a configurable default SP award for NPC registrations.
        event = self.event
        if logistics_periods is None:
            if self.attended_periods:
                logistics_periods = self.attended_periods
            else:
                logistics_periods = self.default_logistics_periods
        logistics_periods = max(
            min(event.logistics_periods, logistics_periods), Decimal(0)
        )
        xp = int(_XP_PER_HALFDAY * logistics_periods)

        return AwardRecord(
            date=event.event_end_date.date(),
            source_id=event.pk,
            character=self.character_id,
            category=AwardCategory.EVENT,
            description=f"{self.pc_npc} Event Credit for {event}",
            event_xp=xp,
            event_cp=1 if xp > 0 else 0,
            # Events that grant no XP don't flag the PC as "played"
            event_played=(not self.is_npc) if xp > 0 else False,
            event_staffed=self.is_npc,
        )

    @property
    def is_canceled(self):
        return bool(self.canceled_date)

    @property
    def profile(self) -> account_models.Membership:
        profile = account_models.Membership.objects.filter(
            game=self.event.campaign.game,
            user=self.user,
        ).first()
        if profile is not None:
            return profile
        # If a user somehow registers without a profile, return one anyway.
        return account_models.Membership(
            game=self.event.campaign.game,
            user=self.user,
            birthdate=datetime.date.today(),
        )

    @property
    def pc_npc(self) -> str:
        return "NPC" if self.is_npc else "PC"

    @property
    def player_is_new(self) -> bool:
        player_data = game_models.PlayerCampaignData.retrieve_model(
            self.user, self.event.campaign, update=False
        )
        record = player_data.record
        return (record.events_played + record.events_staffed) < 1

    @property
    def npc_is_new(self) -> bool:
        player_data = game_models.PlayerCampaignData.retrieve_model(
            self.user, self.event.campaign, update=False
        )
        record = player_data.record
        return record.events_staffed < 1

    @property
    def character_is_new(self) -> bool:
        if self.is_npc:
            return False
        if character := self.character:
            if metadata := character.metadata:
                return metadata.events_played < 1
        return False

    @transaction.atomic
    def apply_award(
        self, applied_by: User, logistics_periods: int | Decimal | None = None
    ) -> None:
        if not self.event.completed:
            raise ValueError(
                f"Can't apply credit for event '{self.event}' until it is completed."
            )
        if self.canceled_date is not None:
            raise ValueError("Registration was withdrawn")
        if self.attended:
            # TODO: Support revising a previously applied award.
            raise ValueError("Already marked attendance for this player")
        if logistics_periods is None:
            if self.attended_periods:
                logistics_periods = self.attended_periods
            else:
                logistics_periods = self.default_logistics_periods
        self.attended = True
        self.attended_periods = logistics_periods
        self.award_applied_by = applied_by
        self.award_applied_date = timezone.now()
        campaign = self.event.campaign

        award = self.award_record(logistics_periods=logistics_periods)

        player_data = game_models.PlayerCampaignData.retrieve_model(
            user=self.user,
            campaign=campaign,
            update=False,
        )
        player_record = player_data.record
        player_data.record = player_record.update(campaign.record, [award])
        player_data.save()

    @property
    def default_logistics_periods(self) -> Decimal:
        match self.attendance:
            case Attendance.FULL:
                logistics_periods = self.event.logistics_periods
            case Attendance.DAY:
                logistics_periods = Decimal(2)
            case _:
                logging.warning(
                    "Unknown attendance type %s", self.get_attendance_label()
                )
                logistics_periods = Decimal(0)
        return logistics_periods

    def get_absolute_url(self):
        return reverse(
            "registration-view",
            kwargs={"pk": self.event.pk, "username": self.user.username},
        )

    def __str__(self) -> str:
        name = self.user.username
        if self.is_npc:
            return f"{self.event} - {name} (NPC)"
        if self.character:
            return f"{self.event} - {name} ({self.character.name})"
        return f"{self.event} - {name} (Unfinished)"

    class Meta:
        unique_together = [
            ["event", "user"],
        ]

        indexes = [
            models.Index(fields=["event", "user"], name="game-event-user-idx"),
            models.Index(
                fields=["event", "character"], name="game-event-character-idx"
            ),
        ]

        rules_permissions = {
            "view": game_models.is_self | game_models.can_manage_events,
            "add": game_models.is_self | game_models.can_manage_events,
            "change": game_models.is_self | game_models.can_manage_events,
            "delete": game_models.is_self | game_models.can_manage_events,
        }


def _task_uuid():
    return f"report-{uuid.uuid4().hex}"


class EventReport(RulesModel):
    event: Event = models.ForeignKey(
        Event, related_name="reports", on_delete=models.CASCADE
    )
    started = models.DateTimeField(auto_now_add=True)
    requestor: User = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="event_reports",
        help_text="The user who triggered the report.",
    )
    report_type: str = models.CharField(
        max_length=50,
        help_text="Report type identifier, as used by the trigger-event-report view.",
    )
    content_type: str = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default=None,
        help_text="MIME type of the output, to report to the browser.",
    )
    filename: str = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default=None,
        help_text="Filename to report to the browser. This is NOT a file on the webserver filesystem.",
    )
    blob: str = models.BinaryField(
        null=True,
        default=None,
        help_text="Report file content, once the task is complete.",
    )
    download_ready: bool = models.BooleanField(
        default=False,
        help_text="Marked True by the task once the report download is ready.",
    )
    message: str = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return f"{self.event} {self.report_type}"
