import random
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Users
from apps.reports.models import HazardReports, HazardCategories
from devutils.factories import HazardReportFactory
from devutils.factories.base_factory import SeedData, chance, pick
from devutils.seeders.base_seeder import (
    FORCE_CLOSED_REMARKS,
    INVALID_REPORT_REMARKS,
    ON_HOLD_REMARKS,
    OUT_OF_JURISDICTION_REMARKS,
    RESOLVED_REMARKS,
    AuditEvent,
    AuditEventCollector,
    Progress,
    TRANSFER_REMARKS,
    audit_report_create,
    audit_severity_change,
    audit_status_change,
    backdate,
)
from devutils.seeders.base_seeder import reissue_number
from devutils.seeders.user_seeder import UserSeedResult


@dataclass
class ReportSeedInfo:
    report: HazardReports
    created_at: object
    end_at: object                 # timestamp of the last simulated event
    final_status: str
    path: list[str]                # status values after creation
    assigned_to: Users | None
    initial_status: str = "NEW"    # status label at creation time
    invalid_submission: bool = False       # BEFORE photo comes from AFTER urls
    resolved_at: object | None = None      # set when path reached RESOLVED
    confirmed_at: object | None = None     # set when reporter confirmed CLOSED

    @property
    def needs_resolution_images(self) -> bool:
        return self.resolved_at is not None


# Archetypes: (key, jurisdiction, final_status)
# jurisdiction "oj" = outside Metro Manila → out-of-jurisdiction remarks path.
ARCHETYPES = [
    ("new",           "mm", "NEW"),
    ("assigned",      "mm", "ASSIGNED"),
    ("under_review",  "mm", "UNDER_REVIEW"),
    ("on_hold",       "mm", "ON_HOLD"),
    ("dispatched",    "mm", "DISPATCHED"),
    ("ongoing",       "mm", "ONGOING"),
    ("resolved",      "mm", "RESOLVED"),
    ("closed_conf",   "mm", "CLOSED"),
    ("invalid",       "mm", "INVALID"),
    ("oj_hold",       "oj", "ON_HOLD"),
    ("oj_closed",     "oj", "CLOSED"),
]

FILL_WEIGHTS = [
    ("new", 6), ("assigned", 8), ("under_review", 10), ("on_hold", 8),
    ("dispatched", 9), ("ongoing", 9), ("resolved", 9), ("closed_conf", 12),
    ("invalid", 9), ("oj_hold", 6), ("oj_closed", 6),
]

# Ordered status path AFTER creation for each archetype. Every consecutive
# pair is valid per STATUS_ALLOWED_TRANSITIONS, and ASSIGNED only ever leads
# to UNDER_REVIEW (server-enforced rule).
PATHS: dict[str, list[str]] = {
    "new":          [],
    "assigned":     [],
    "under_review": ["UNDER_REVIEW"],
    "on_hold":      ["UNDER_REVIEW", "ON_HOLD"],
    "dispatched":   ["UNDER_REVIEW", "DISPATCHED"],
    "ongoing":      ["UNDER_REVIEW", "DISPATCHED", "ONGOING"],
    "resolved":     ["UNDER_REVIEW", "DISPATCHED", "ONGOING", "RESOLVED"],
    "closed_conf":  ["UNDER_REVIEW", "DISPATCHED", "ONGOING", "RESOLVED", "CLOSED"],
    "invalid":      ["UNDER_REVIEW", "INVALID"],
    "oj_hold":      ["UNDER_REVIEW", "ON_HOLD"],
    "oj_closed":    ["UNDER_REVIEW", "ON_HOLD", "CLOSED"],
}

SEVERITY_BAG_WEIGHTS = ["P3", "P3", "P4", "P4", "P4", "P2", "P2", "P5", "P5", "P1"]


def _build_archetype_plan(count: int) -> list[tuple[str, str, str]]:
    """Guarantee every archetype appears (when count allows), then fill
    randomly with weights so states are distributed realistically."""
    plan: list[tuple[str, str, str]] = []
    for arch in ARCHETYPES:
        if len(plan) >= count:
            break
        plan.append(arch)

    keys = [k for k, _ in FILL_WEIGHTS]
    weights = [w for _, w in FILL_WEIGHTS]
    while len(plan) < count:
        key = random.choices(keys, weights=weights, k=1)[0]
        plan.append(next(a for a in ARCHETYPES if a[0] == key))

    random.shuffle(plan)
    return plan


def _severity_bag():
    """Guarantees P1..P5 all appear (first five yields) before randomizing."""
    coverage = ["P1", "P2", "P3", "P4", "P5"]
    random.shuffle(coverage)
    yield from coverage
    while True:
        yield random.choice(SEVERITY_BAG_WEIGHTS)


def _gap() -> timedelta:
    """Time between two simulated workflow steps (2h .. 72h)."""
    return timedelta(hours=random.randint(2, 72))


def run(
    *,
    progress: Progress,
    events: AuditEventCollector,
    counts: dict,
    users: UserSeedResult,
) -> list[ReportSeedInfo]:
    categories = list(HazardCategories.objects.filter(is_active=True))
    if not categories:
        raise RuntimeError("No hazard categories found — run sync_db first.")

    officers = [u for u in users.assignment_pool if u.is_active]
    citizen_pool = list(users.citizens)
    if not citizen_pool:
        raise RuntimeError("No active citizens available for reports.")

    report_count = counts["reports"]
    plan = _build_archetype_plan(report_count)
    sev_iter = _severity_bag()
    infos: list[ReportSeedInfo] = []

    # Without officers, assignment-based archetypes degrade to fresh reports.
    if not officers:
        plan = [("new", juris, "NEW") for _, juris, _ in plan]

    for index, (arch_key, juris, _final) in enumerate(plan, start=1):
        info = _generate_report(
            arch_key=arch_key,
            juris=juris,
            categories=categories,
            officers=officers,
            citizen_pool=citizen_pool,
            events=events,
            sev_iter=sev_iter,
        )
        infos.append(info)
        path_str = " -> ".join([info.initial_status, *info.path]) \
            if info.path else info.initial_status
        progress.step(
            f"Report {index}/{report_count} {info.report.report_number} "
            f"-> {info.final_status} ({path_str})"
        )

    _apply_transfers(progress, events, infos, users)
    return infos


# ---------------------------------------------------------------------------

def _generate_report(
    *,
    arch_key: str,
    juris: str,
    categories: list,
    officers: list,
    citizen_pool: list,
    events: AuditEventCollector,
    sev_iter,
) -> ReportSeedInfo:
    category = pick(categories)
    location = (
        pick(SeedData.outside_metro_manila_locations())
        if juris == "oj"
        else pick(SeedData.metro_manila_locations())
    )
    reporter = pick(citizen_pool)
    assigned_officer = pick(officers)

    planned_path = PATHS[arch_key]

    # Creation flavor: some reports are created already-assigned (staff was
    # available at submit time), others start NEW then get system-assigned —
    # mirrors create_assign_hazard_report vs _process_unassigned_reports.
    system_assigns = arch_key != "new" and chance(0.4)
    born_assigned = arch_key != "new" and not system_assigns

    created_at = _report_creation_time(len(planned_path) + (1 if system_assigns else 0))

    report = HazardReportFactory(
        reported_by=reporter,
        assigned_to=assigned_officer if born_assigned else None,
        category=category,
        status=(
            HazardReports.Status.ASSIGNED
            if born_assigned
            else HazardReports.Status.NEW
        ),
        is_anonymous=chance(0.2),
        _location=location,
        due_at=created_at + timedelta(days=category.response_time_days),
    )
    backdate(report, created_at, ["created_at"])
    reissue_number(report, "report_number", "REPT", created_at)
    report.save(update_fields=["report_number"])

    initial_label = report.status.label
    audit_report_create(
        ev=events,
        actor=reporter,
        report=report,
        assigned_to=assigned_officer if born_assigned else None,
        at=created_at,
    )

    cursor = created_at
    path: list[str] = []

    # System auto-assignment (NEW → ASSIGNED by the System, actor=None).
    if system_assigns:
        cursor += _gap()
        report.status = HazardReports.Status.ASSIGNED
        report.assigned_to = assigned_officer
        report.save(update_fields=["status", "assigned_to"])
        audit_status_change(
            ev=events, actor=None, report=report,
            old_status="New", new_status="Assigned", at=cursor,
        )
        path.append("ASSIGNED")

    severity_set = False
    resolved_at = None
    confirmed_at = None
    invalid_submission = False

    for i, next_status in enumerate(planned_path):
        remarks_pool = _remarks_pool(next_status, juris)

        # Mandatory severity gate: UNDER_REVIEW → ON_HOLD / DISPATCHED
        # requires a triage severity (mirrors MandatorySeverityStatusError).
        if next_status in ("ON_HOLD", "DISPATCHED") and not severity_set:
            cursor += timedelta(hours=random.randint(1, 10))
            new_sev = next(sev_iter)
            old_sev = report.severity
            report.severity = new_sev
            report.save(update_fields=["severity"])
            audit_severity_change(
                ev=events, actor=_actor(report, officers), report=report,
                old_severity=old_sev, new_severity=new_sev, at=cursor,
            )
            severity_set = True

        cursor += _gap()
        actor = _actor(report, officers)
        old_label = report.status.label

        # RESOLVED → CLOSED here is the reporter-confirmation path
        # (confirm_report_resolution): confirmed_at set, remarks untouched.
        is_confirm_close = (
            next_status == "CLOSED"
            and HazardReports.Status(report.status) == HazardReports.Status.RESOLVED
        )

        report.status = HazardReports.Status(next_status)
        update_fields = ["status"]

        if is_confirm_close:
            report.confirmed_at = cursor
            confirmed_at = cursor
            update_fields.append("confirmed_at")
        else:
            # update_authorized_assigned_report overwrites remarks on every
            # status change; mandatory statuses (ON_HOLD/CLOSED/INVALID)
            # must carry a non-empty value.
            remarks = pick(remarks_pool) if remarks_pool else None
            report.remarks = remarks
            update_fields.append("remarks")

        # RESOLVED: DO 47 resolution requirements (validated works).
        if next_status == "RESOLVED":
            report.validated_by_name = _random_technician_name()
            report.validated_by = actor
            report.resolved_at = cursor
            resolved_at = cursor
            update_fields += ["validated_by_name", "validated_by", "resolved_at"]

        report.save(update_fields=update_fields)
        new_label = report.status.label

        audit_status_change(
            ev=events,
            actor=report.reported_by if is_confirm_close else actor,
            report=report,
            old_status=old_label,
            new_status=new_label,
            at=cursor,
            remarks="Resolution confirmed by the reporter." if is_confirm_close
                    else (report.remarks if "remarks" in update_fields else None),
        )

        if next_status == "INVALID":
            invalid_submission = True

        path.append(next_status)

    end_at = cursor
    if end_at >= timezone.now():
        # Extremely unlikely with workflow-aware backdating; keep data sane.
        end_at = timezone.now() - timedelta(hours=1)

    return ReportSeedInfo(
        report=report,
        created_at=created_at,
        end_at=end_at,
        final_status=report.status,
        path=path,
        assigned_to=report.assigned_to,
        initial_status=initial_label,
        invalid_submission=invalid_submission,
        resolved_at=resolved_at,
        confirmed_at=confirmed_at,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _remarks_pool(next_status: str, juris: str) -> list[str]:
    """Pool of staff remarks written on the transition INTO next_status.

    Mandatory-remarks statuses always pick from their pool; RESOLVED gets
    the rectification note routinely recorded by resolving officers (it then
    survives the confirm-to-closed path, which never overwrites remarks).
    Other transitions return [] and leave remarks None, exactly like a staff
    update sent without remarks.
    """
    if next_status == "ON_HOLD":
        if juris == "oj":
            return OUT_OF_JURISDICTION_REMARKS
        return ON_HOLD_REMARKS
    if next_status == "INVALID":
        return INVALID_REPORT_REMARKS
    if next_status == "CLOSED":
        if juris == "oj":
            return OUT_OF_JURISDICTION_REMARKS + FORCE_CLOSED_REMARKS
        return FORCE_CLOSED_REMARKS
    if next_status == "RESOLVED":
        return RESOLVED_REMARKS
    return []


def _actor(report: HazardReports, officers: list) -> Users | None:
    if report.assigned_to_id:
        return report.assigned_to
    return pick(officers) if officers else None


def _random_technician_name() -> str:
    from devutils.factories.base_factory import random_filipino_name
    first, last = random_filipino_name()
    return f"Engr. {first} {last}"


def _report_creation_time(steps: int):
    """Backdate creation far enough to fit the simulated workflow plus a
    random age buffer; short paths get recent creations so some reports are
    not yet overdue while older ones are."""
    from devutils.seeders.base_seeder import random_past_datetime
    workflow_days = steps * 3          # generous: avg step ~1.6 days
    if steps <= 1:
        age_days = random.randint(1, 12)
    else:
        age_days = workflow_days + random.randint(5, 40)
    jitter = timedelta(hours=random.randint(0, 23))
    return timezone.now() - timedelta(days=age_days) - jitter


# ---------------------------------------------------------------------------
# Transfers (TRANSFER audit coverage; phase 1-3 reports only, as enforced
# by ReportService.transfer_report)
# ---------------------------------------------------------------------------

def _apply_transfers(
    progress: Progress,
    events: AuditEventCollector,
    infos: list[ReportSeedInfo],
    users: UserSeedResult,
) -> None:
    officers = [u for u in users.assignment_pool if u.is_active]
    if len(officers) < 2:
        progress.detail("Skipping transfer simulation (need 2+ officers).")
        return

    eligible = [
        i for i in infos
        if i.report.assigned_to_id
        and HazardReports.Status(i.report.status).phase < 4
    ]
    if not eligible:
        return

    actor = pick(users.warn_actors) if users.warn_actors else None

    for info in random.sample(eligible, min(2, len(eligible))):
        current = info.report.assigned_to
        candidates = [o for o in officers if o.user_id != current.user_id]
        if not candidates:
            continue
        target = pick(candidates)
        at = info.end_at + timedelta(hours=random.randint(2, 48))
        if at >= timezone.now():
            at = timezone.now() - timedelta(hours=1)

        info.report.assigned_to = target
        info.report.save(update_fields=["assigned_to"])
        info.assigned_to = target

        remarks = pick(TRANSFER_REMARKS)
        actor_str = actor.user_number if actor else target.user_number
        desc = (
            f"REPORT {info.report.report_number} was transferred from "
            f"{current.user_number} to {target.user_number} by {actor_str}"
        )
        if remarks:
            desc += f' with the remarks: "{remarks}"'

        events.add(AuditEvent(
            occurred_at=at,
            action="TRANSFER",
            module="REPORT",
            actor=actor,
            target=info.report,
            description=desc,
            payload={
                "assignment_change": {"from": current.email, "to": target.email},
                "remarks": remarks,
            },
        ))
        info.end_at = at
        progress.detail(
            f"Transferred {info.report.report_number}: "
            f"{current.user_number} -> {target.user_number}"
        )
