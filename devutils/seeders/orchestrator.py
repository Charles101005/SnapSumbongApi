from django.core.management import call_command
from django.db import transaction

from devutils.seeders.base_seeder import (
    AuditEventCollector,
    Progress,
)
from devutils.seeders import (
    audit_seeder,
    image_seeder,
    report_seeder,
    user_seeder,
    warning_seeder,
)
from devutils.seeders.clean import clean_dummy_data, has_generated_data


def run(
    *,
    progress: Progress,
    counts: dict,
    clean: bool,
    password: str | None,
    clean_only: bool = False,
) -> dict:
    """Seed the database with interconnected dummy data.

    Order matters: sync default data first, then users (roles must exist),
    then reports (need users), images/warnings (need reports), and finally
    the audit logs (all events collected along the way).

    With clean_only=True the run stops right after the cleanup step.
    """
    if clean_only:
        clean = True  # --clean-only implies cleaning

    # sync (1) + optional cleanup (1) + five seeder sections + summary (1);
    # a clean-only run skips the seeder sections and the summary.
    section_total = 1 + (1 if clean else 0) + (0 if clean_only else 6)
    progress.start(section_total)

    progress.section("Syncing database and default data")
    call_command("sync_db")
    call_command("sync_initial_roles")
    progress.done("Migrations, permissions, initial roles and hazard categories synced")

    # Fail fast instead of colliding with a previous run's role codes /
    # emails halfway through: stacked runs without --clean always break
    # uniqueness constraints. Checked after sync so the tables exist even
    # on a fresh database.
    if not clean and has_generated_data():
        raise RuntimeError(
            "Previously generated dummy data found. Re-run with --clean "
            "(wipe, then regenerate) or --clean-only (wipe only) to remove "
            "it first (default roles, permissions, categories and manually "
            "created accounts are kept)."
        )

    if clean:
        progress.section("Cleaning previously seeded dummy data")
        clean_dummy_data(progress)

    if clean_only:
        return {"cleaned_only": True}

    events = AuditEventCollector()

    with transaction.atomic():
        progress.section("Creating roles and accounts")
        users = user_seeder.run(
            progress=progress,
            events=events,
            counts=counts,
            password=password,
        )

        progress.section("Creating hazard reports")
        infos = report_seeder.run(
            progress=progress,
            events=events,
            counts=counts,
            users=users,
        )

        progress.section("Attaching report images")
        image_counts = image_seeder.run(progress=progress, infos=infos)

        progress.section("Issuing warnings and moderation actions")
        moderation = warning_seeder.run(
            progress=progress,
            events=events,
            counts=counts,
            infos=infos,
            users=users,
        )

        progress.section("Writing audit logs")
        audit_count = audit_seeder.run(progress=progress, events=events)

    progress.section("Summary")
    summary = _build_summary(users, infos, image_counts, moderation, audit_count)
    return summary


def _build_summary(users, infos, image_counts, moderation, audit_count) -> dict:
    status_totals: dict[str, int] = {}
    for info in infos:
        key = str(info.final_status)
        status_totals[key] = status_totals.get(key, 0) + 1

    return {
        "staff": len(users.all_staff),
        "citizens": len(users.citizens),
        "deactivated_citizens": len(users.deactivated_citizens),
        "custom_roles": len(users.custom_roles),
        "reports": len(infos),
        "report_statuses": status_totals,
        "images": image_counts,
        "warnings": moderation.get("warnings", 0),
        "banned": moderation.get("banned", 0),
        "unbanned": moderation.get("unbanned", 0),
        "audit_logs": audit_count,
    }
