from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import VerificationRequest


class Command(BaseCommand):
    help = (
        "Delete verification requests (OTP / password-reset rows) that expired "
        "more than ABANDONED_THRESHOLD ago. Schedule this command hourly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would be deleted without deleting them.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            threshold = settings.VERIFICATION_REQUEST_CONFIG["ABANDONED_THRESHOLD"]
            cutoff = timezone.now() - threshold
            count = VerificationRequest.objects.filter(expires_at__lte=cutoff).count()
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: {count} abandoned verification request(s) would "
                    "be deleted."
                )
            )
            return

        deleted_count, _ = VerificationRequest.objects.delete_abandoned()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} abandoned verification request(s)."
            )
        )
