from django.core.management.base import BaseCommand, CommandError

from apps.reports.services import ReportService


class Command(BaseCommand):
    help = (
        "Email the reporter of each open report that has passed its due date. "
        "Each report is notified at most once ever. Schedule this command "
        "daily (cron, Task Scheduler, or the deployment platform's scheduler)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many reports would be notified without sending.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5,
            help="Maximum number of report rows handled per query batch.",
        )

    def handle(self, *args, **options):
        if options["batch_size"] <= 0:
            raise CommandError("--batch-size must be greater than zero.")

        result = ReportService.notify_overdue_reports(
            dry_run=options["dry_run"],
            batch_size=options["batch_size"],
        )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: {result['would_notify']} overdue report(s) "
                    "would be notified."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Notified {result['notified']} overdue report(s); "
                f"skipped {result['skipped']}, failed {result['failed']}."
            )
        )
