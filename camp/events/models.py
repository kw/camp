import datetime

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rules.contrib.models import RulesModel

from ..character import models as char_models
from ..game import models as game_models
from ..game import rules

User = get_user_model()


class Month(models.IntegerChoices):
    JAN = 1
    FEB = 2
    MAR = 3
    APR = 4
    MAY = 5
    JUN = 6
    JUL = 7
    AUG = 8
    SEPT = 9
    OCT = 10
    NOV = 11
    DEC = 12


class Event(RulesModel):
    name: str = models.CharField(max_length=100, blank=True)
    description: str = models.TextField(blank=True)
    location: str = models.TextField(blank=True)
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
        help_text="When should the Register button be shown, in the chapter's local timezone? Leave blank to open immediately.",
    )
    registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When should the Register button go away, in the chapter's local timezone? Leave blank to open until end-of-event.",
    )
    event_start_date = models.DateField()
    event_end_date = models.DateField()

    logistics_periods = models.DecimalField(
        max_digits=4, decimal_places=2, help_text="How many long rests?"
    )
    logistics_year = models.IntegerField(
        blank=True,
        default=0,
        help_text="What year of the campaign is this event in? Must match the event start or end date.",
    )
    logistics_month = models.IntegerField(
        blank=True,
        default=0,
        choices=Month.choices,
        help_text=(
            "What month of the campaign should this be counted as? "
            "Must match the event start or end date."
        ),
    )

    def save(self, *args, **kwargs):
        # The logistics month defaults to the end date of the event.
        if not self.logistics_year:
            self.logistics_year = self.event_end_date.year
        if not self.logistics_month:
            self.logistics_month = self.event_end_date.month

        # If a logistics month is specified that doesn't correspond to either
        # the start of the event or the end of the event, reset it.
        valid_logi_periods = {
            (self.event_start_date.year, self.event_start_date.month),
            (self.event_end_date.year, self.event_end_date.month),
        }
        if (self.logistics_year, self.logistics_month) not in valid_logi_periods:
            self.logistics_year = self.event_end_date.year
            self.logistics_month = self.event_end_date.month

        if not self.name:
            self.name = str(self)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.name:
            effective_name = self.name
        else:
            effective_name = (
                f"{self.chapter} {self.logistics_year}-{self.logistics_month}"
            )
        if self.is_canceled:
            effective_name = f"{effective_name} [CANCELED]"
        return effective_name

    def get_absolute_url(self):
        return reverse("event-detail", kwargs={"pk": self.pk})

    def registration_window_open(self):
        now = timezone.now()
        if self.registration_open and now < self.registration_open:
            return False
        if self.registration_deadline and now > self.registration_deadline:
            return False
        # If no registration deadline was specified, we don't allow registration
        # past the end of the event.
        if (
            not self.registration_deadline
            and datetime.date.today() > self.event_end_date
        ):
            return False
        return True

    def event_in_progress(self):
        return self.event_start_date <= datetime.date.today() <= self.event_end_date

    @property
    def is_canceled(self):
        return bool(self.canceled_date)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="end_date_gte_start",
                violation_error_message="End date must not be before start date.",
                check=Q(event_end_date__gte=F("event_start_date")),
            ),
        ]

        indexes = [
            models.Index(
                fields=["campaign", "chapter", "logistics_year", "logistics_month"],
                name="campaign-year-month-idx",
            ),
        ]

        rules_permissions = {
            "view": rules.always_allow,
            "add": rules.can_manage_events,
            "change": rules.can_manage_events,
            "delete": rules.can_manage_events,
        }


class EventRegistration(RulesModel):
    # You can't delete an event once people start signing up for it.
    # You can still cancel the event, but the registrations persist in case
    # there is payment or other information attached.
    event: Event = models.ForeignKey(
        Event, related_name="event_registrations", on_delete=models.PROTECT
    )
    # But if a user is deleted, clear them out.
    user: User = models.ForeignKey(
        User, related_name="event_registrations", on_delete=models.CASCADE
    )
    is_npc: bool = models.BooleanField()
    details: str = models.TextField(blank=True)

    # Maybe we should force NPCs to select a character to receive credit?
    # OR we could just let them select it later.
    character: char_models.Character = models.ForeignKey(
        char_models.Character,
        related_name="event_registrations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # By default we'll take the primary character sheet.
    sheet: char_models.Sheet = models.ForeignKey(
        char_models.Sheet,
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
    attended: bool = models.BooleanField(default=False)
    attended_periods = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    @property
    def logistics_window(self) -> tuple[int, int]:
        return self.event.logistics_year, self.event.logistics_month

    def __str__(self) -> str:
        name = self.user.first_name or self.user.username
        if self.is_npc:
            return f"{self.event} - {name} (NPC)"
        return f"{self.event} - {name} ({self.character.name})"

    class Meta:
        unique_together = [
            ["event", "user"],
        ]

        indexes = [
            models.Index(fields=["event", "user"], name="event-user-idx"),
            models.Index(fields=["event", "character"], name="event-character-idx"),
        ]

        rules_permissions = {
            "view": rules.is_self | rules.is_chapter_logistics,
            "add": rules.is_self | rules.is_chapter_logistics,
            "change": rules.is_self | rules.is_chapter_logistics,
            "delete": rules.is_self | rules.is_chapter_logistics,
        }
