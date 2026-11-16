from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from devutils.base import DebugOnlyCommand


class Command(DebugOnlyCommand):
    help = (
        "Drain the unassigned NEW hazard report backlog using the same "
        "round-robin sweep that runs when a report is submitted."
    )

    def handle(self, *args, **options):
        pending = self._pending_count()

        if pending == 0:
            self.stdout.write(self.style.SUCCESS("No pending NEW reports to assign."))
            return

        self.stdout.write(f"Pending NEW reports: {pending}")

        assigned = 0

        while pending:
            before = pending
            ReportService._process_unassigned_reports()
            pending = self._pending_count()
            progressed = before - pending

            if progressed == 0:
                self.stdout.write(self.style.WARNING(
                    "Stopped: no eligible active staff are available for assignment."
                ))
                break

            assigned += progressed
            self.stdout.write(f"Assigned {progressed} report(s); {pending} remaining.")

        self.stdout.write(self.style.SUCCESS(
            f"Assigned {assigned} report(s); {pending} still pending."
        ))

    @staticmethod
    def _pending_count() -> int:
        return HazardReports.objects.filter(
            status=HazardReports.Status.NEW,
            assigned_to__isnull=True,
        ).count()
