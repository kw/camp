import pprint
import sys
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from camp.game.models import Campaign
from camp.game.models import Event


class DryRun(Exception):
    pass


class Command(BaseCommand):
    help = "Recomputes campaign records."

    def add_arguments(self, parser):
        parser.add_argument("campaign_id", type=str)
        parser.add_argument("-e", "--events", nargs="+", type=int)
        parser.add_argument("-n", "--dry-run", action="store_true", default=False)
        parser.add_argument("-y", "--yes", action="store_true", default=False)
        parser.add_argument("--start-year", type=int)

    def handle(
        self,
        campaign_id: str,
        events: list[int] | None = None,
        dry_run=False,
        yes=False,
        start_year: int | None = None,
        **options,
    ):
        committed = False
        try:
            with transaction.atomic():

                campaign = Campaign.objects.get(slug=campaign_id)
                prev_record = campaign.record

                if start_year and campaign.start_year != start_year:
                    campaign.start_year = start_year

                if events:
                    for eid in events:
                        event = Event.objects.get(id=eid)
                        if event.completed:
                            self.stdout.write(
                                self.style.NOTICE(
                                    f"{event} already completed, skipping"
                                )
                            )
                        else:
                            event.completed = True
                            event.save()
                            self.stdout.write(
                                self.style.SUCCESS(f"{event} marked complete.")
                            )

                event_records = [
                    e.record for e in campaign.events.filter(completed=True)
                ]
                self.stdout.write(f"Re-ingesting {len(event_records)} events.")
                new_record = prev_record.model_copy(
                    update={
                        "values_table": [],
                        "recent_events": [],
                        "start_year": campaign.start_year,
                        "last_event_date": date(campaign.start_year, 1, 1),
                    }
                ).add_events(event_records)
                prev_record_format = pprint.pformat(prev_record.model_dump(mode="json"))
                new_record_format = pprint.pformat(new_record.model_dump(mode="json"))
                self.stdout.write(f"\nPrevious campaign record:\n{prev_record_format}")
                self.stdout.write(f"\nNew campaign record:\n{new_record_format}")

                if prev_record == new_record:
                    self.stdout.write("(Previous and new records are identical)")

                if not yes:
                    input("Press enter to continue or Ctrl-C to abort.")

                campaign.record = new_record
                campaign.save()

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
