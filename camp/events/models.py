from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F
from django.db.models import Q
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
    OCT = 10
    NOV = 11
    DEC = 12


class Event(RulesModel):
    name: str = models.CharField(max_length=100, blank=True)
    description: str = models.TextField(blank=True)
    location: str = models.TextField(blank=True)
    details_template: str = models.TextField(blank=True)

    chapter: game_models.Chapter = models.ForeignKey(
        game_models.Chapter, on_delete=models.PROTECT, related_name="events"
    )
    campaign: game_models.Campaign = models.ForeignKey(
        game_models.Campaign, on_delete=models.PROTECT, related_name="events"
    )
    creator: User = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    registration_open = models.DateTimeField(null=True, blank=True)
    registration_deadline = models.DateTimeField(null=True, blank=True)
    event_start_date = models.DateField()
    event_end_date = models.DateField()

    logistics_periods = models.DecimalField(max_digits=4, decimal_places=2)
    logistics_year = models.IntegerField(blank=True, default=0)
    logistics_month = models.IntegerField(blank=True, default=0, choices=Month.choices)

    def save(self, *args, **kwargs):
        if not self.logistics_year:
            self.logistics_year = self.event_end_date.year
        if not self.logistics_month:
            self.logistics_month = self.event_end_date.month
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.campaign}, {self.chapter}, {self.logistics_year}-{self.logistics_month}"
            + (f": {self.name}" if self.name else "")
        )

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="end_date_gte_start",
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
            "add": rules.is_chapter_logistics,
            "change": rules.is_chapter_logistics,
            "delete": rules.is_chapter_logistics,
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
