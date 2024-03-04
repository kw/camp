"""Campaign models.

These models calculate specific campaign-wide values based on event history.
Specifically, the cadence of game events controls the rate at which the
Campaign Max XP, CP, and Bonus CP levels rise over the course of the campaign.

Note that these models largely only contain enough data to perform calculations with.
The web app's models in camp.game.models will contain the "real" campaign/event info,
and will be responsible for creating, populating, persisting, and regenerating these
lower-level models as necessary.

For more details, see:
https://docs.google.com/document/d/1qva8lxQqHIJZ-vl4OWU7cu_9i2uaUc_1AGjQPgHGzNA/edit
"""

from __future__ import annotations

import bisect
import datetime
from collections import defaultdict
from typing import Callable

from pydantic import BaseModel
from pydantic import Field
from pydantic import NonNegativeInt
from pydantic import TypeAdapter
from pydantic import ValidationInfo
from pydantic import field_validator

# Used for sorting/searching through events and value entries
DATE_KEY: Callable[[EventRecord | CampaignValues], datetime.date] = lambda e: e.date


class EventRecord(BaseModel, frozen=True, extra="forbid"):
    """Representation of game event.

    The representation is pared down to only what is necessary in this module.
    Full representation of an event is typically kept elsewhere.

    Attributes:
        chapter: A key identifying a chapter. If for some reason a chapter wants
            to change whatever value they're using for their key, that should work
            fine as long as it remains consistent within a month.
        date: The date the event ends and its impact on the campaign becomes effective.
        xp_value: The XP awarded by this event. Normally equal to 2 times the number of half-days,
            or 8 for a typical weekend event.
        cp_value: The CP awarded by this event. Normally equal to 1 as long as any XP was awarded.
    """

    chapter: str
    date: datetime.date
    xp_value: NonNegativeInt = 8  # Most events are 8 XP.
    cp_value: NonNegativeInt = 1


class CampaignValues(BaseModel, frozen=True, extra="forbid"):
    """Campaign-wide progression tracking values.

    These values change over the course of a campaign. A table stored in
    the Campaign object tracks their change over time.

    Attributes:
        date: The date when these values are effective.
        max_xp: The maximum XP a player could have at this point in time,
            including XP from the event ending this date.
        max_cp: The maximum Event CP a character could have at this point in time,
            including CP from the event ending this date.
        max_bonus_cp: The maximum Bonus CP a character could have at this point in time.
            Determined solely by the season of the event (what year it happened).
    """

    date: datetime.date
    max_xp: int
    max_cp: int
    max_bonus_cp: int

    @property
    def floor_xp(self) -> int:
        """The minimum amount of XP a player can have at this time."""
        return self.max_xp // 2

    @property
    def floor_cp(self) -> int:
        """The minimum amount of Event CP a character can have at this time."""
        return self.max_cp // 2


class CampaignRecord(BaseModel, frozen=True):
    """Represents the campaign as a whole over time.

    Attributes:
        name: The name of the campaign, mainly so that test campaign data is
            identified as such if seen in logs.
        value_table: List of CampaignValues
        events: List of all events that have place.
    """

    name: str
    start_year: int
    bonus_cp_per_season: int = 3
    value_table: list[CampaignValues] = Field(default_factory=list)
    events: list[EventRecord] = Field(default_factory=list)
    last_event_date: datetime.date = datetime.date(1, 1, 1)

    @property
    def season(self) -> int:
        return self.last_event_date.year - self.start_year + 1

    @property
    def start_values(self) -> CampaignValues:
        return CampaignValues(
            date=datetime.date(self.start_year, 1, 1),
            max_xp=0,
            max_cp=0,
            max_bonus_cp=3,
        )

    @property
    def latest_values(self) -> CampaignValues:
        """The latest effective value set for this campaign, according to its event history."""
        if self.value_table:
            return self.value_table[-1]
        return self.start_values

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

    @property
    def floor_xp(self) -> int:
        """The minimum amount of XP a player can have at this time."""
        return self.max_xp // 2

    @property
    def floor_cp(self) -> int:
        """The minimum amount of Event CP a character can have at this time."""
        return self.max_cp // 2

    def add_events(self, new_events: list[EventRecord]) -> CampaignRecord:
        """Integrates events into the value table."""
        if not new_events:
            return self

        last_event_date = self.last_event_date

        all_events = sorted(set(self.events + new_events), key=DATE_KEY)

        value_table = []

        # 1. Group all events by logistics month
        months: dict[tuple[int, int], list[EventRecord]] = defaultdict(list)
        for event in all_events:
            events = months[event.date.year, event.date.month]
            events.append(event)

        month_keys = sorted(months.keys())
        last_values = self.get_historical_values(
            all_events[0].date - datetime.timedelta(days=1)
        )

        # 2. For each logistics month, in ascending order:
        for logi_month in month_keys:
            # a. Sort events within the month by end date, ascending
            events = months[logi_month]
            events.sort(key=DATE_KEY)

            # b. Start a tracker for Max XP/CP for each chapter for the month,
            #    initializing each to the last month’s ending values (or 0 if this is the first month).
            start_max_xp = last_values.max_xp
            start_max_cp = last_values.max_cp
            max_xp: dict[str, int] = defaultdict(lambda: start_max_xp)
            max_cp: dict[str, int] = defaultdict(lambda: start_max_cp)

            # c. For each event:
            for event in events:
                if event.date > last_event_date:
                    last_event_date = event.date

                # i. Add the event’s XP and CP values to its chapter’s tracker.
                chapter = event.chapter

                max_xp[chapter] += event.xp_value
                max_cp[chapter] += event.cp_value

                # ii. If either of the new values are now the highest out of all chapters,
                #     write a new table entry (dated at the event’s end date) that contains
                #     the new max values across each chapter’s tracker.
                new_max_xp = max(max_xp.values())
                new_max_cp = max(max_cp.values())

                if new_max_xp > last_values.max_xp or new_max_cp > last_values.max_cp:
                    season = event.date.year - self.start_year + 1
                    last_values = CampaignValues(
                        date=event.date,
                        max_xp=new_max_xp,
                        max_cp=new_max_cp,
                        max_bonus_cp=season * self.bonus_cp_per_season,
                    )
                    # Skip any values we've already covered, and, crucially,
                    # ignore anything that would change historical records.
                    if not value_table or value_table[-1].date < last_values.date:
                        value_table.append(last_values)

        return self.model_copy(
            update={
                "value_table": value_table,
                "events": all_events,
                "last_event_date": last_event_date,
            }
        )

    def get_historical_values(self, effective_date: datetime.date) -> CampaignValues:
        """Determine the campaign values on a particular date in the past."""
        i = bisect.bisect_right(self.value_table, effective_date, key=DATE_KEY)
        if i:
            return self.value_table[i - 1]
        return self.start_values

    @field_validator("value_table")
    @classmethod
    def validate_entries_sorted(
        cls, v: list[EventRecord], info: ValidationInfo
    ) -> list[EventRecord]:
        """Enforce that the value table must be sorted by date, otherwise we can't search it."""
        if not v:
            return v
        for i in range(1, len(v)):
            if v[i - 1].date > v[i].date:
                raise ValueError("Entries must be sorted by date")
        return v


CampaignAdapter = TypeAdapter(CampaignRecord)
