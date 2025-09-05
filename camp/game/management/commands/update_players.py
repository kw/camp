import sys

from django.core.management.base import BaseCommand
from django.db import transaction

from camp.game.models import Campaign
from camp.game.models import PlayerCampaignData


class DryRun(Exception):
    pass


class Command(BaseCommand):
    help = "Recomputes player records."

    def add_arguments(self, parser):
        parser.add_argument("-c", "--campaign_id", type=str)
        parser.add_argument("-p", "--players", nargs="+", type=str)
        parser.add_argument(
            "-r", "--regenerate_awards", action="store_true", default=False
        )
        parser.add_argument("-n", "--dry-run", action="store_true", default=False)

    def handle(
        self,
        campaign_id: str | None = None,
        players: list[str] | None = None,
        regenerate_awards: bool = False,
        dry_run=False,
        **options,
    ):
        committed = False
        try:
            with transaction.atomic():
                query = PlayerCampaignData.objects
                if campaign_id:
                    campaign = Campaign.objects.get(slug=campaign_id)
                    query = query.filter(campaign=campaign)
                if players:
                    query = query.filter(user__username__in=players)

                updated = 0
                total = query.count()
                self.stdout.write(f"Regenerating {total} player records")
                for pd in query.all():
                    try:
                        prev_record = pd.record
                    except Exception:
                        self.stdout.write("Error reading previous record.")
                        prev_record = None
                    if regenerate_awards or not prev_record:
                        new_record = pd.regenerate_awards()
                    else:
                        new_record = prev_record.regenerate(pd.campaign.record)
                    if new_record != prev_record:
                        pd.record = new_record
                        pd.save()
                        updated += 1

                    self.stdout.write(f"Updating {pd}\n")
                    self.stdout.write(f"Previous: {prev_record}\n")
                    self.stdout.write(f"New: {new_record}\n\n")

                self.stdout.write(f"Updated {updated}/{total} records")

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
