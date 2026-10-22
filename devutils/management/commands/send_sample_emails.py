import secrets
import string
from typing import Any, Callable

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone

from devutils.base import DebugOnlyCommand
from external.email import EmailService
from apps.reports.models import HazardReports
from shared.utils import model_number_generator


class Command(DebugOnlyCommand):
    help = (
        "Sends a sample of every EmailService email to one recipient (dev only). "
        "Recipient details are prompted for; everything else is mocked with the "
        "same formats the app actually produces. Use --list to see the samples "
        "and --only to send a subset."
    )

    SAMPLE_SUBMITTED_AT_FORMAT = "%B %d, %Y at %I:%M %p"
    SAMPLE_LOCATION = "123 Rizal Avenue, Barangay San Isidro, Quezon City"
    SAMPLE_CATEGORY = "Potholes"
    SAMPLE_REMARKS = "Crew dispatched. Repair scheduled within the SLA window."
    SAMPLE_BAN_REASON = "Repeated invalid or inaccurate hazard reports after multiple warnings."
    SAMPLE_ASSIGNED_ROLE = "Supervisor"
    SAMPLE_TEMP_PASSWORD = "K1sRJB*z1mgX"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--list",
            action="store_true",
            help="List the available sample emails without sending anything.",
        )
        parser.add_argument(
            "--only",
            type=str,
            default=None,
            help="Comma-separated sample keys to send (default: all). See --list.",
        )
        parser.add_argument(
            "--email",
            type=str,
            default=None,
            help="Recipient email. Prompted when omitted.",
        )
        parser.add_argument(
            "--first-name",
            type=str,
            default=None,
            help="Recipient first name. Prompted when omitted.",
        )
        parser.add_argument(
            "--last-name",
            type=str,
            default=None,
            help="Recipient last name (used for the deactivation sample's full name). Prompted when omitted.",
        )

    # ------------------------------------------------------------------
    # Sample collection
    # ------------------------------------------------------------------
    def _otp_code(self) -> str:
        length: int = settings.VERIFICATION_REQUEST_CONFIG["OTP_LENGTH"]
        return "".join(secrets.choice(string.digits) for _ in range(length))

    @staticmethod
    def _expiry_minutes() -> int:
        lifetime = settings.VERIFICATION_REQUEST_CONFIG["VERIFICATION_REQUEST_LIFETIME"]
        return int(lifetime.total_seconds() // 60)

    def _build_context(self, *, email: str, first_name: str, last_name: str) -> dict[str, Any]:
        # Every value here is a mock, but each one follows the real format the
        # app produces (REPT-/LOG-/USER- numbers, status labels, date layout).
        report_number = model_number_generator("REPT")

        return {
            "email": email,
            "first_name": first_name,
            "full_name": f"{last_name}, {first_name}",
            "otp_code": self._otp_code(),
            "expiry_minutes": self._expiry_minutes(),
            "report_number": report_number,
            "category": self.SAMPLE_CATEGORY,
            "location": self.SAMPLE_LOCATION,
            "submitted_at": timezone.localtime(timezone.now()).strftime(
                self.SAMPLE_SUBMITTED_AT_FORMAT
            ),
            "old_status": HazardReports.Status.ASSIGNED.label,
            "new_status": HazardReports.Status.UNDER_REVIEW.label,
            "case_id": model_number_generator("LOG"),
            "flagged_report_count": 2,
            "total_report_count": 5,
            "reason": self.SAMPLE_BAN_REASON,
            "flagged_report_numbers": [
                model_number_generator("REPT"),
                model_number_generator("REPT"),
            ],
            "user_number": model_number_generator("USER"),
            "assigned_role": self.SAMPLE_ASSIGNED_ROLE,
            "temp_password": self.SAMPLE_TEMP_PASSWORD,
        }

    def _samples(self, ctx: dict[str, Any]) -> list[tuple[str, str, Callable[[], bool]]]:
        """(key, description, send callable) for every EmailService method,
        including both renderings of the status-update template."""
        email = ctx["email"]
        first_name = ctx["first_name"]

        return [
            (
                "registration_otp",
                "send_registration_otp -- 4-digit registration verification code",
                lambda: EmailService.send_registration_otp(
                    to_email=email,
                    to_first_name=first_name,
                    otp_code=ctx["otp_code"],
                    expiry_minutes=ctx["expiry_minutes"],
                ),
            ),
            (
                "password_reset_otp",
                "send_password_reset_otp -- forgot-password verification code",
                lambda: EmailService.send_password_reset_otp(
                    to_email=email,
                    to_first_name=first_name,
                    otp_code=ctx["otp_code"],
                    expiry_minutes=ctx["expiry_minutes"],
                ),
            ),
            (
                "email_change_otp",
                "send_email_change_otp -- new-email verification code",
                lambda: EmailService.send_email_change_otp(
                    to_email=email,
                    to_first_name=first_name,
                    otp_code=ctx["otp_code"],
                    expiry_minutes=ctx["expiry_minutes"],
                ),
            ),
            (
                "report_submission",
                "send_report_successful_submission -- report receipt",
                lambda: EmailService.send_report_successful_submission(
                    to_email=email,
                    to_first_name=first_name,
                    report_number=ctx["report_number"],
                    category=ctx["category"],
                    location=ctx["location"],
                    submitted_at=ctx["submitted_at"],
                ),
            ),
            (
                "status_update_with_remarks",
                "send_report_status_update -- status change with crew remarks",
                lambda: EmailService.send_report_status_update(
                    to_email=email,
                    to_first_name=first_name,
                    report_number=ctx["report_number"],
                    category=ctx["category"],
                    location=ctx["location"],
                    submitted_at=ctx["submitted_at"],
                    old_status=ctx["old_status"],
                    new_status=ctx["new_status"],
                    remarks=self.SAMPLE_REMARKS,
                ),
            ),
            (
                "status_update_no_remarks",
                "send_report_status_update -- status change, remarks block hidden",
                lambda: EmailService.send_report_status_update(
                    to_email=email,
                    to_first_name=first_name,
                    report_number=ctx["report_number"],
                    category=ctx["category"],
                    location=ctx["location"],
                    submitted_at=ctx["submitted_at"],
                    old_status=ctx["old_status"],
                    new_status=ctx["new_status"],
                    remarks="",
                ),
            ),
            (
                "user_banned",
                "send_user_banned -- ban notice with case reference",
                lambda: EmailService.send_user_banned(
                    to_email=email,
                    to_first_name=first_name,
                    case_id=ctx["case_id"],
                    flagged_report_count=ctx["flagged_report_count"],
                    total_report_count=ctx["total_report_count"],
                    reason=ctx["reason"],
                    flagged_report_numbers=ctx["flagged_report_numbers"],
                ),
            ),
            (
                "self_deactivation",
                "send_user_self_deactivation -- confirmation of account deactivation",
                lambda: EmailService.send_user_self_deactivation(
                    to_email=email,
                    to_first_name=first_name,
                    full_name=ctx["full_name"],
                ),
            ),
            (
                "employee_temp_password",
                "send_employee_creation_temporary_password -- new staff credentials",
                lambda: EmailService.send_employee_creation_temporary_password(
                    to_email=email,
                    to_first_name=first_name,
                    user_number=ctx["user_number"],
                    assigned_role=ctx["assigned_role"],
                    temp_password=ctx["temp_password"],
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # Input helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _prompt_value(label: str, provided: str|None) -> str:
        if provided is not None and provided.strip():
            return provided.strip()

        while True:
            value = input(f"{label}: ").strip()
            if value:
                return value
            print(f"  {label} cannot be empty.")

    def _resolve_selection(self, only: str|None, samples: list[tuple[str, str, Any]]) -> list[tuple[str, str, Any]]:
        if not only:
            return samples

        available = [key for key, _, _ in samples]
        requested = [key.strip() for key in only.split(",") if key.strip()]

        unknown = [key for key in requested if key not in available]
        if unknown:
            raise CommandError(
                f"Unknown sample key(s): {', '.join(unknown)}. "
                f"Available: {', '.join(available)}"
            )

        requested_set = set(requested)
        return [sample for sample in samples if sample[0] in requested_set]

    # ------------------------------------------------------------------
    def handle(self, *args, **options) -> None:
        # Fixed up front so --list works without prompting for a recipient.
        if options["list"]:
            self._list_samples()
            return

        email = self._prompt_value("Recipient email", options["email"])
        first_name = self._prompt_value("Recipient first name", options["first_name"])
        last_name = self._prompt_value("Recipient last name", options["last_name"])

        ctx = self._build_context(email=email, first_name=first_name, last_name=last_name)
        samples = self._resolve_selection(options["only"], self._samples(ctx))

        if not samples:
            raise CommandError("No samples selected.")

        self.stdout.write(self.style.NOTICE(
            f"Sending {len(samples)} sample email(s) to {email}.\n"
            "In dev each one is also printed to the terminal by EmailService.\n"
        ))

        sent = 0
        for index, (key, description, send) in enumerate(samples, start=1):
            self.stdout.write(self.style.NOTICE(
                f"[{index}/{len(samples)}] {key} -- {description}"
            ))

            if send():
                sent += 1
                self.stdout.write(self.style.SUCCESS(f"  ok: {key}"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"  FAILED: {key} (Resend rejected or errored -- check RESEND_API_KEY)"
                ))

            self.stdout.write("")

        summary = f"Sent {sent}/{len(samples)} sample emails."
        if sent == len(samples):
            self.stdout.write(self.style.SUCCESS(summary))
        else:
            self.stdout.write(self.style.WARNING(summary))

    def _list_samples(self) -> None:
        ctx = self._build_context(email="<prompted>", first_name="<prompted>", last_name="<prompted>")

        self.stdout.write("Available sample keys (--only key1,key2):")
        for key, description, _ in self._samples(ctx):
            self.stdout.write(f"  {key:<28} {description}")

        self.stdout.write("\nMocked values used for this run's formats:")
        self.stdout.write(f"  report_number : {ctx['report_number']}")
        self.stdout.write(f"  case_id       : {ctx['case_id']}")
        self.stdout.write(f"  user_number   : {ctx['user_number']}")
        self.stdout.write(f"  otp_code      : {ctx['otp_code']}")
        self.stdout.write(f"  expiry_minutes: {ctx['expiry_minutes']}")
        self.stdout.write(f"  status        : {ctx['old_status']} -> {ctx['new_status']}")
        self.stdout.write(f"  category      : {ctx['category']}")
        self.stdout.write(f"  location      : {ctx['location']}")
        self.stdout.write(f"  submitted_at  : {ctx['submitted_at']}")
        self.stdout.write(f"  flagged       : {ctx['flagged_report_count']} of {ctx['total_report_count']} submitted")
