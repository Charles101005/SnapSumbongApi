from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.reports.services import ReportService


class Command(BaseCommand):
    help = (
        "Automatically close RESOLVED reports whose reporter confirmation "
        "window has elapsed. Schedule this command daily (cron, Task "
        "Scheduler, or the deployment platform's scheduler)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=(
                "Override the confirmation window in days. Defaults to "
                "REPORT_CONFIG['RESOLVED_AUTO_CLOSE_AFTER_DAYS']."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many reports would close without changing them.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Maximum number of report rows handled per query batch.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days is None:
            days = settings.REPORT_CONFIG.get(
                "RESOLVED_AUTO_CLOSE_AFTER_DAYS", 7
            )
        if days < 0:
            raise CommandError("--days must be zero or greater.")
        if options["batch_size"] <= 0:
            raise CommandError("--batch-size must be greater than zero.")

        result = ReportService.auto_close_resolved_reports(
            older_than_days=days,
            dry_run=options["dry_run"],
            batch_size=options["batch_size"],
        )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run: "
                    f"{result['would_close']} resolved report(s) would be "
                    f"auto-closed after {days} day(s)."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Auto-closed {result['closed']} resolved report(s); "
                f"skipped {result['skipped']}, failed {result['failed']} "
                f"(window: {days} day(s))."
            )
        )
