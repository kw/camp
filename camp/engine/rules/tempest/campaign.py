from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import Field
from pydantic import model_validator

from ..base_models import BaseModel


class Event(BaseModel):
    chapter: str
    start_date: datetime.date
    end_date: datetime.date
    logi_periods: Decimal = Decimal(-1)

    @model_validator(mode="after")
    def validate(self):
        if self.end_date < self.start_date:
            raise ValueError(f"Event {self} has invalid start and end dates")

        duration = self.end_date - self.start_date
        if duration.days > 7:
            raise ValueError(f"Event {self} has unlikely duration ({duration} days)")

        if self.logi_periods < 0:
            self.logi_periods = max(
                Decimal((self.end_date - self.start_date).days * 2), Decimal(0.5)
            )


class CampaignValues(BaseModel):
    effective_date: datetime.date
    max_xp: int = 0
    max_cp: int = 0
    max_bonus_cp: int = 3


class Campaign(BaseModel):
    name: str

    historical_events: list[Event] = Field(default_factory=list)
    value_table: list[CampaignValues] = Field(default_factory=list)

    @property
    def latest_values(self) -> CampaignValues:
        """The latest effective value set for this campaign, according to its event history."""
        if self.value_table:
            return self.value_table[-1]
        return CampaignValues(effective_date=datetime.date(1, 1, 1))

    @property
    def max_xp(self) -> int:
        """Campaign Max Event XP.

        Since Event XP is the only kind of XP at this time, this is the sole number determining
        the XP level of a player. All of a player's characters have the same XP, regardless of when
        they are created.
        """
        return self.latest_values.max_xp

    @property
    def max_cp(self) -> int:
        """Campaign Max Event CP.

        This is the amount of CP that a character could earn from normal event attendance.
        If they attend more events than this, extra CP will be go into Bonus CP, if that's
        not also at its max level.
        """
        return self.latest_values.max_cp

    @property
    def max_bonus_cp(self) -> int:
        """Campaign Max Bonus CP.

        This is equal to 3 per _season_ of the campaign.
        """
        return self.latest_values.max_bonus_cp

    def add_events(self, new_events: list[Event]) -> None:
        """Integrates events into the event history, recalculating the value table if needed."""
        # TODO: Make this better/faster
        self.historical_events = sorted(
            self.historical_events + new_events, key=lambda e: e.end_date
        )
        # TODO: Make this actually do something
        self.value_table = []

    def get_historical_values(self, effective_date) -> CampaignValues:
        """Determine the campaign values on a particular date in the past."""
        # TODO: Make this actually do something.
        return self.latest_values
