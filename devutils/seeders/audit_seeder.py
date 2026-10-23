from devutils.seeders.base_seeder import (
    AuditEventCollector,
    Progress,
    write_audit_events,
)


def run(*, progress: Progress, events: AuditEventCollector) -> int:
    """Persist every collected audit event in chronological order with
    backdated created_at and matching audit_log_number dates."""
    count = write_audit_events(events.sorted_events())
    progress.done(f"{count} audit logs written")
    return count
