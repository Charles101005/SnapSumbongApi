import random
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports
from devutils.factories import AuditLogFactory


class Progress:
    """Prints step-by-step progress for the seeder run."""

    def __init__(self, stdout, style):
        self.stdout = stdout
        self.style = style
        self.section_total = 0
        self.section_index = 0

    def start(self, total_sections: int) -> None:
        self.section_total = total_sections
        self.section_index = 0

    def section(self, title: str) -> None:
        self.section_index += 1
        self.stdout.write(
            self.style.NOTICE(
                f"[{self.section_index}/{self.section_total}] {title}"
            )
        )

    def step(self, message: str) -> None:
        self.stdout.write(f"  -> {message}")

    def detail(self, message: str) -> None:
        self.stdout.write(f"      {message}")

    def done(self, message: str) -> None:
        self.stdout.write(self.style.SUCCESS(f"  [OK] {message}"))


# ---------------------------------------------------------------------------
# Time helpers — reports are backdated so timelines look organic and the
# analytics/date filters have spread-out data to work with.
# ---------------------------------------------------------------------------

def random_past_datetime(min_days_ago: int, max_days_ago: int):
    days = random.randint(min_days_ago, max_days_ago)
    hours = random.randint(0, 23)
    minutes = random.randint(0, 59)
    return timezone.now() - timedelta(days=days, hours=hours, minutes=minutes)


def backdate(instance, timestamp, update_fields: list[str]) -> None:
    """Set created_at/updated_at explicitly.

    Uses queryset.update() so auto_now/auto_now_add pre_save hooks are
    bypassed and the backdated values actually persist.
    """
    values = {fname: timestamp for fname in update_fields}
    type(instance).objects.filter(pk=instance.pk).update(**values)
    for fname, value in values.items():
        setattr(instance, fname, value)


def reissue_number(instance, field_name: str, prefix: str, when,
                   suffix_length: int = 6) -> None:
    """Regenerate a model_number_generator-style number stamped with `when`
    instead of today, keeping uniqueness. The caller persists it afterwards."""
    import secrets
    import string as _string

    choices = _string.digits + _string.ascii_uppercase
    date_str = when.strftime("%Y%m%d")
    model = type(instance)
    while True:
        suffix = "".join(secrets.choice(choices) for _ in range(suffix_length))
        candidate = f"{prefix}-{date_str}-{suffix}"
        if not model.objects.filter(**{field_name: candidate}).exists():
            setattr(instance, field_name, candidate)
            return


# ---------------------------------------------------------------------------
# Remarks / status transition helpers
# ---------------------------------------------------------------------------

OUT_OF_JURISDICTION_REMARKS = [
    "Out of jurisdiction \u2014 location is outside Metro Manila. "
    "Referred to the concerned LGU for proper action.",
    "Out of jurisdiction \u2014 site falls outside DO 47 coverage. "
    "Endorsed to the local government unit of the reported area.",
    "Out of jurisdiction \u2014 area is outside Metro Manila and belongs to "
    "another engineering district. Forwarded to the appropriate office.",
    "Out of jurisdiction \u2014 property is maintained by the provincial "
    "government. Referred for appropriate action.",
]

INVALID_REPORT_REMARKS = [
    "Photo submitted does not match the reported hazard or location \u2014 "
    "invalid submission, flagged for moderation.",
    "Submission photo appears to be unrelated stock imagery; report cannot "
    "be verified on site. Marked invalid.",
    "Report details and photo are inconsistent with the actual site; "
    "flagged as invalid after verification.",
    "Photo does not show any hazard at the declared coordinates. "
    "Report marked invalid.",
]

ON_HOLD_REMARKS = [
    "On hold pending coordination with the barangay engineering office.",
    "On hold \u2014 awaiting clearance from the traffic management unit "
    "before crews can be dispatched.",
    "On hold \u2014 external department has yet to respond regarding the "
    "referred concern.",
    "On hold \u2014 awaiting availability of heavy equipment for the "
    "scheduled rectification works.",
]

FORCE_CLOSED_REMARKS = [
    "Force-closed by staff \u2014 referred out to the responsible agency "
    "and no further action required from this office.",
    "Force-closed by staff \u2014 report is outside DO 47 jurisdiction; "
    "no confirming party responded within the closure window.",
    "Force-closed by staff \u2014 hazard could not be reproduced on site "
    "after two validation visits.",
]

# Staff routinely record what was done when resolving (not mandatory, but
# it keeps the internal notes realistic and survives the confirm-to-closed
# path, which never overwrites remarks).
RESOLVED_REMARKS = [
    "Pothole patched and compacted; pavement restored to serviceable condition.",
    "Damaged drainage grate replaced and secured.",
    "Debris cleared and the affected lane reopened to traffic.",
    "Roadcut backfilled and compacted; area safe for passage.",
    "Damaged signpost reinstalled and realigned.",
    "Collapsed shoulder repaired and warning delineators reset.",
]

SEVERITY_REMARKS = {
    "P1": "Critical \u2014 immediate danger to the public, expedited response required.",
    "P2": "High \u2014 significant hazard affecting regular traffic flow.",
    "P3": "Medium \u2014 standard hazard scheduled within the normal response window.",
    "P4": "Low \u2014 minor concern, can be consolidated with nearby works.",
    "P5": "Very low \u2014 cosmetic or informational; queued for routine maintenance.",
}

TRANSFER_REMARKS = [
    "Reassigned due to workload balancing.",
    "Handed off \u2014 original handler is on leave.",
    "Transferred to the officer covering the reported area.",
    None,
]


def pick_remarks(pool: list[str]) -> str:
    return random.choice(pool)


# ---------------------------------------------------------------------------
# Audit event stream — seeders append events; audit_seeder writes them all
# chronologically at the end so created_at timestamps line up with the
# simulated history.
# ---------------------------------------------------------------------------

@dataclass
class AuditEvent:
    occurred_at: object          # datetime
    action: str                  # AuditLogs.ActionType value
    module: str                  # AuditLogs.ModuleType value
    description: str
    target: object               # model instance (Users / Roles / HazardReports)
    actor: object | None = None  # Users instance or None (system)
    payload: dict = field(default_factory=dict)


class AuditEventCollector:
    def __init__(self):
        self.events: list[AuditEvent] = []

    def add(self, event: AuditEvent) -> None:
        self.events.append(event)

    def sorted_events(self) -> list[AuditEvent]:
        return sorted(self.events, key=lambda e: e.occurred_at)

    def __len__(self) -> int:
        return len(self.events)


def write_audit_events(events: list[AuditEvent]) -> int:
    """Create AuditLogs rows in chronological order with backdated created_at
    and audit_log_numbers stamped to match each event's simulated date."""
    count = 0
    for ev in events:
        log = AuditLogFactory(
            user=ev.actor,
            action=ev.action,
            module=ev.module,
            description=ev.description[:255],
            payload=ev.payload,
            target_object=ev.target,
        )
        # audit_log_number is editable=False but settable on the instance;
        # save() keeps any non-empty value.
        reissue_number(log, "audit_log_number", "LOG", ev.occurred_at)
        log.save(update_fields=["audit_log_number"])
        backdate(log, ev.occurred_at, ["created_at"])
        count += 1
    return count


# Convenience wrappers mirroring AuditLogService wording -------------------

def audit_report_create(*, ev: AuditEventCollector, actor, report, assigned_to, at):
    ev.add(AuditEvent(
        occurred_at=at,
        action=AuditLogs.ActionType.CREATE,
        module=AuditLogs.ModuleType.REPORT,
        actor=actor,
        target=report,
        description=(
            f"REPORT {report.report_number} was created by "
            f"{actor.user_number if actor else 'Unknown'}"
        ),
        payload={
            "initial_status": report.status.label if hasattr(report.status, "label") else report.status,
            "assigned_to": assigned_to.email if assigned_to else None,
        },
    ))


def audit_status_change(*, ev: AuditEventCollector, actor, report,
                        old_status, new_status, at, remarks=None, payload_override=None):
    actor_str = actor.user_number if actor else "the System"
    remarks_str = (
        f' with the remarks: "{remarks}"' if remarks else ""
    )
    description = (
        f"REPORT {report.report_number} status was changed from "
        f"{old_status.upper()} to {new_status.upper()} by {actor_str}"
        f"{remarks_str}"
    )
    payload = payload_override or {
        "status_change": {"from": old_status, "to": new_status},
        "remarks": remarks,
    }
    ev.add(AuditEvent(
        occurred_at=at,
        action=AuditLogs.ActionType.STATUS_CHANGE,
        module=AuditLogs.ModuleType.REPORT,
        actor=actor,
        target=report,
        description=description,
        payload=payload,
    ))


def audit_severity_change(*, ev: AuditEventCollector, actor, report,
                          old_severity, new_severity, at):
    actor_str = actor.user_number if actor else "the System"
    ev.add(AuditEvent(
        occurred_at=at,
        action=AuditLogs.ActionType.SEVERITY_CHANGE,
        module=AuditLogs.ModuleType.REPORT,
        actor=actor,
        target=report,
        description=(
            f"REPORT {report.report_number} severity was changed from "
            f"{old_severity} to {new_severity} by {actor_str}"
        ),
        payload={"severity_change": {"from": old_severity, "to": new_severity}},
    ))
