from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError

from devutils.base import DebugOnlyCommand

# NOTE: factory_boy/faker-pulling modules (dev-only dependencies) are
# imported lazily inside handle(), so merely listing or running this command
# in production never imports them; DebugOnlyCommand blocks DEBUG-off runs.

# Interactive defaults; --non-interactive (or explicit flags) skips prompts.
DEFAULT_COUNTS = {
    "system_admins": 1,
    "supervisors": 2,
    "report_officers": 3,
    "citizens": 30,
    "custom_roles": 2,
    "reports": 50,
}

# Warnings are derived from the report volume, mirroring how moderation
# warnings arise from INVALID reports (kept in the 5-10 range).
WARNING_MIN, WARNING_MAX = 5, 10


class Command(DebugOnlyCommand):
    help = (
        "Generate realistic, interconnected dummy data for local development: "
        "accounts for every default role, optional custom roles, hazard "
        "reports covering every status and severity, report images, citizen "
        "warnings with ban/unban states, and matching audit logs. "
        "Use --clean to wipe and regenerate, or --clean-only to just wipe. "
        "Only runs when DEBUG=True."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--system-admins", type=int,
            help=f"Number of SYSTEM_ADMIN accounts (default: {DEFAULT_COUNTS['system_admins']}).",
        )
        parser.add_argument(
            "--supervisors", type=int,
            help=f"Number of SUPERVISOR accounts (default: {DEFAULT_COUNTS['supervisors']}).",
        )
        parser.add_argument(
            "--report-officers", type=int,
            help=f"Number of REPORT_OFFICER accounts (default: {DEFAULT_COUNTS['report_officers']}).",
        )
        parser.add_argument(
            "--citizens", type=int,
            help=f"Number of CITIZEN accounts (default: {DEFAULT_COUNTS['citizens']}).",
        )
        parser.add_argument(
            "--custom-roles", type=int,
            help=f"Number of extra custom roles to create (default: {DEFAULT_COUNTS['custom_roles']}).",
        )
        parser.add_argument(
            "--reports", type=int,
            help=f"Number of hazard reports to create (default: {DEFAULT_COUNTS['reports']}).",
        )
        parser.add_argument(
            "--clean", action="store_true",
            help="Remove previously seeded dummy data before generating "
                 "(default roles, permissions, categories and manually "
                 "created accounts are kept).",
        )
        parser.add_argument(
            "--clean-only", action="store_true",
            help="Remove previously seeded dummy data and stop, without "
                 "generating anything new (implies --clean; no prompts).",
        )
        parser.add_argument(
            "--non-interactive", action="store_true",
            help="Skip prompts and use defaults (or the values passed via flags).",
        )
        parser.add_argument(
            "--password", type=str, default=None,
            help="Password shared by every generated account "
                 "(defaults to the dev-only common password; must pass the "
                 "configured password validators).",
        )

    def handle(self, *args, **options):
        # Lazy imports: factories/seeders pull in faker + factory_boy, which
        # are dev-only dependencies.
        from devutils.factories.base_factory import COMMON_PASSWORD
        from devutils.seeders.base_seeder import Progress
        from devutils.seeders.orchestrator import run as run_seeding

        clean_only = options["clean_only"]

        if clean_only:
            # Cleanup only: no generation, so passwords/counts are irrelevant.
            self._warn_if_counts_passed(options)
            password = None
            counts = None
        else:
            password = options["password"] or COMMON_PASSWORD

            try:
                validate_password(password)
            except ValidationError as exc:
                raise CommandError(
                    "The provided --password does not meet the password "
                    "complexity requirements: " + " ".join(exc.messages)
                )

            counts = self._resolve_counts(options)
            warnings = max(
                WARNING_MIN,
                min(WARNING_MAX, max(WARNING_MIN, counts["reports"] // 5)),
            )
            counts["warnings"] = warnings

        progress = Progress(self.stdout, self.style)

        if clean_only:
            self.stdout.write(
                self.style.NOTICE("\nRemoving previously generated dummy data...")
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    "\nGenerating dummy data with the following counts:"
                )
            )
            for label, value in [
                ("SYSTEM_ADMIN accounts", counts["system_admins"]),
                ("SUPERVISOR accounts", counts["supervisors"]),
                ("REPORT_OFFICER accounts", counts["report_officers"]),
                ("CITIZEN accounts", counts["citizens"]),
                ("Custom roles", counts["custom_roles"]),
                ("Hazard reports", counts["reports"]),
                ("Citizen warnings (derived)", counts["warnings"]),
            ]:
                self.stdout.write(f"  - {label}: {value}")
            if options["clean"]:
                self.stdout.write("  - Existing dummy data will be cleaned first")
            self.stdout.write("")

        try:
            summary = run_seeding(
                progress=progress,
                counts=counts or {},
                clean=options["clean"] or clean_only,
                password=password,
                clean_only=clean_only,
            )
        except RuntimeError as exc:
            raise CommandError(str(exc))

        if clean_only:
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS("Generated dummy data removed.")
            )
            return

        self._print_summary(summary)

    # -----------------------------------------------------------------------

    def _warn_if_counts_passed(self, options) -> None:
        passed = [
            flag for flag in (
                "system_admins", "supervisors", "report_officers",
                "citizens", "custom_roles", "reports",
            )
            if options.get(flag) is not None
        ]
        if passed:
            self.stdout.write(self.style.WARNING(
                "--clean-only: ignoring count flags (--"
                + ", --".join(passed)
                + "); no new data will be generated."
            ))

    def _resolve_counts(self, options) -> dict:
        counts = dict(DEFAULT_COUNTS)

        flag_map = {
            "system_admins": "system_admins",
            "supervisors": "supervisors",
            "report_officers": "report_officers",
            "citizens": "citizens",
            "custom_roles": "custom_roles",
            "reports": "reports",
        }

        for key, flag in flag_map.items():
            if options[flag] is not None:
                counts[key] = options[flag]

        if options["non_interactive"]:
            return counts

        prompts = [
            ("system_admins", "Number of SYSTEM_ADMIN accounts"),
            ("supervisors", "Number of SUPERVISOR accounts"),
            ("report_officers", "Number of REPORT_OFFICER accounts"),
            ("citizens", "Number of CITIZEN accounts"),
            ("custom_roles", "Number of extra custom roles"),
            ("reports", "Number of hazard reports"),
        ]

        for key, label in prompts:
            if options.get(key) is not None:
                # Already provided via flag; don't re-ask.
                continue
            counts[key] = self._prompt_int(label, counts[key])

        return counts

    def _prompt_int(self, label: str, default: int) -> int:
        while True:
            raw = input(f"{label} [{default}]: ").strip()
            if not raw:
                return default
            try:
                value = int(raw)
            except ValueError:
                self.stdout.write(self.style.WARNING("Please enter a whole number."))
                continue
            if value < 0:
                self.stdout.write(self.style.WARNING("Please enter zero or more."))
                continue
            return value

    def _print_summary(self, summary: dict) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Dummy data generated successfully."))
        self.stdout.write(f"  Staff accounts:        {summary['staff']}")
        self.stdout.write(f"  Citizen accounts:      {summary['citizens']} "
                          f"(+{summary['deactivated_citizens']} deactivated)")
        self.stdout.write(f"  Custom roles:          {summary['custom_roles']}")
        self.stdout.write(f"  Hazard reports:        {summary['reports']}")
        for status, total in sorted(summary["report_statuses"].items()):
            self.stdout.write(f"      - {status}: {total}")
        images = summary["images"]
        self.stdout.write(
            f"  Report images:         {images['BEFORE']} before, "
            f"{images['DURING']} during, {images['AFTER']} after"
        )
        self.stdout.write(f"  Citizen warnings:      {summary['warnings']}")
        self.stdout.write(f"  Bans / unbans:         {summary['banned']} / {summary['unbanned']}")
        self.stdout.write(f"  Audit logs:            {summary['audit_logs']}")
