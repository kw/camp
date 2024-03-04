import argparse
import csv
import io
import logging
import pprint
import sys
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from camp.engine.rules.tempest.records import AwardCategory
from camp.engine.rules.tempest.records import AwardRecord
from camp.game.models import Campaign
from camp.game.models import Chapter
from camp.game.models import Event
from camp.game.models.game_models import Award


class DryRun(Exception):
    pass


EVENT_DATE = "Event Date"
EMAIL = "Email Address"
PLAYER = "Player Name"
CHARACTER = "Character Name"
TYPE = "Type"
PERIODS = "Attended"


class Command(BaseCommand):
    help = "Import event attendance data from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("campaign_id", type=str)
        parser.add_argument("chapter_id", type=str)
        parser.add_argument("infile", type=argparse.FileType("r"))
        parser.add_argument("-n", "--dry-run", action="store_true", default=False)

    def handle(
        self,
        campaign_id: str,
        chapter_id: str,
        infile: io.TextIOBase,
        dry_run=False,
        **options,
    ):
        committed = False
        try:
            with transaction.atomic():
                campaign = Campaign.objects.get(slug=campaign_id)
                chapter = Chapter.objects.get(slug=chapter_id)
                all_events = Event.objects.filter(campaign=campaign, chapter=chapter)
                events = {e.event_end_date.strftime("%Y-%m-%d"): e for e in all_events}
                missing_events = set()
                for entry in csv.DictReader(infile):
                    event_date = entry[EVENT_DATE].strip()
                    event = events.get(event_date)
                    parsed_date = datetime.strptime(event_date, "%Y-%m-%d").date()
                    if not event:
                        if event_date not in missing_events:
                            logging.warning(
                                "No event in %s ending on %s", chapter, event_date
                            )
                            missing_events.add(event_date)
                    email = entry[EMAIL].strip()
                    player_name = entry[PLAYER].strip()
                    char_name = entry[CHARACTER].strip()
                    attend_type = entry[TYPE].strip()
                    logi_periods = int(entry[PERIODS].strip())
                    event_xp = logi_periods * 2

                    is_npc = attend_type.lower() == "npc"
                    description = (
                        f"Imported {attend_type} credit for {event or event_date}"
                    )
                    if not is_npc and char_name:
                        description += f": {char_name}"

                    record = AwardRecord(
                        date=parsed_date,
                        source_id=event.id if event else None,
                        category=AwardCategory.EVENT,
                        description=description,
                        event_xp=event_xp,
                        event_cp=1,
                        event_played=not is_npc,
                        event_staffed=is_npc,
                    )
                    record_data = record.model_dump(mode="json", exclude_defaults=True)

                    self.stdout.write(
                        f"Creating record for {player_name} ({email}):\n{pprint.pformat(record_data)}"
                    )
                    Award.objects.create(
                        campaign=campaign,
                        email=email,
                        award_data=record_data,
                        chapter=chapter,
                        event=event,
                    )

                if dry_run:
                    raise DryRun()
                committed = True
        except DryRun:
            self.stdout.write(self.style.NOTICE("Dry run, rolled back"))

        if dry_run and committed:
            self.stdout.write(
                self.style.ERROR("Dry run requested but committed anyway.")
            )
            sys.exit(1)
        if committed and not dry_run:
            self.stdout.write(self.style.SUCCESS("Completed successfully."))
