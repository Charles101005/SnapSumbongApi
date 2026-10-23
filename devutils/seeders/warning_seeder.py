import random
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import CitizenWarnings
from devutils.factories import CitizenWarningFactory
from devutils.factories.base_factory import chance, pick
from devutils.seeders.base_seeder import (
    AuditEvent,
    AuditEventCollector,
    Progress,
    backdate,
    reissue_number,
)
from devutils.seeders.report_seeder import ReportSeedInfo
from devutils.seeders.user_seeder import UserSeedResult

# Mirrors ModerationService.BAN_WARNING_THRESHOLD
BAN_WARNING_THRESHOLD = 3

BAN_REASONS = [
    "Repeated submission of hoax or unverifiable hazard reports after "
    "multiple moderation warnings.",
    "Accumulated moderation warnings for invalid and abusive report content.",
    "Persistent misuse of the reporting platform despite prior warnings.",
]

UNBAN_REASONS = [
    "Citizen completed the required appeal and acknowledged the community "
    "guidelines; ban lifted.",
    "Ban overturned after review of the flagged submissions.",
]

STANDALONE_WARNING_REASONS = [
    "Abusive language directed at responding personnel during report follow-up.",
    "Duplicate spam submissions flooding the report queue.",
    "Used the platform to advertise unrelated services instead of reporting "
    "hazards.",
    "Report details were deliberately altered after staff reached out for "
    "clarification.",
]


def run(
    *,
    progress: Progress,
    events: AuditEventCollector,
    counts: dict,
    infos: list[ReportSeedInfo],
    users: UserSeedResult,
) -> dict:
    warn_actors = [u for u in users.warn_actors if u.is_active]
    if not warn_actors:
        progress.detail("No staff with WARN permission; skipping warnings.")
        return {"warnings": 0, "banned": 0, "unbanned": 0}

    active_citizens = [c for c in users.citizens if c.is_active]
    if not active_citizens:
        progress.detail("No active citizens; skipping warnings.")
        return {"warnings": 0, "banned": 0, "unbanned": 0}

    # Citizens who own at least one INVALID report (linked-warning eligible;
    # the service requires INVALID status, ownership, one warning per report).
    invalid_by_owner = defaultdict(list)
    for info in infos:
        if info.final_status == "INVALID" and info.report.reported_by_id:
            invalid_by_owner[info.report.reported_by].append(info)

    invalid_owners = [c for c in active_citizens if c in invalid_by_owner]

    warning_count_target = counts["warnings"]
    created_warnings = 0
    banned_users = []
    unban_candidates = []
    warning_totals = defaultdict(int)

    # --- citizen A: built up to the ban threshold -------------------------
    # ModerationService counts ANY warning (not only linked ones), so the
    # count-path citizen does not need to own INVALID reports. Prefer a
    # citizen without any, keeping invalid owners free for the fast-track
    # ban below (so both ban styles + the unban appear even on small runs).
    non_owners = [c for c in active_citizens if c not in invalid_by_owner]
    count_ban_citizen = pick(non_owners or invalid_owners or active_citizens)
    linked_for_a = invalid_by_owner.get(count_ban_citizen, [])[:BAN_WARNING_THRESHOLD]

    def issue_warning(citizen, *, at, report_info=None, reason=None):
        nonlocal created_warnings
        actor = pick(warn_actors)
        warning = CitizenWarningFactory(
            user=citizen,
            warned_by=actor,
            report=report_info.report if report_info else None,
            reason=reason or _warning_reason(report_info),
        )
        reissue_number(warning, "warning_number", "WARN", at)
        warning.save(update_fields=["warning_number"])
        backdate(warning, at, ["created_at"])
        created_warnings += 1
        warning_totals[citizen] += 1

        report_number = (
            report_info.report.report_number if report_info else None
        )
        desc = (
            f"{citizen.user_number} was issued a warning by {actor.user_number}"
            f" with the reason: \"{warning.reason}\""
        )
        if report_number:
            desc += f" (linked report: {report_number})"

        events.add(AuditEvent(
            occurred_at=at,
            action="WARNING",
            module="USER",
            actor=actor,
            target=citizen,
            description=desc,
            payload={
                "warning_number": warning.warning_number,
                "reason": warning.reason,
                "report_number": report_number,
            },
        ))
        return warning

    def ban(citizen, *, at, reason, fast_track_report_number=None):
        actor = pick(warn_actors)
        citizen.is_active = False
        citizen.save(update_fields=["is_active"])
        banned_users.append(citizen)

        desc = (
            f"{citizen.user_number} ({citizen.role.role_name}) was banned by "
            f"{actor.user_number} with the reason: \"{reason}\""
        )
        if fast_track_report_number:
            desc += f" (fast-track evidence: {fast_track_report_number})"

        events.add(AuditEvent(
            occurred_at=at,
            action="BAN",
            module="USER",
            actor=actor,
            target=citizen,
            description=desc,
            payload={
                "reason": reason,
                "fast_track_report_number": fast_track_report_number,
            },
        ))

    # --- count-path warnings: linked first, then top-up to threshold -------
    for info in linked_for_a:
        at = _after(info.end_at)
        issue_warning(count_ban_citizen, at=at, report_info=info)
        progress.detail(
            f"Warned {count_ban_citizen.user_number} "
            f"(linked: {info.report.report_number})"
        )
    # The count path sums every warning for a citizen, so the remainder up to
    # the ban threshold is issued as standalone warnings.
    while warning_totals[count_ban_citizen] < BAN_WARNING_THRESHOLD:
        issue_warning(
            count_ban_citizen,
            at=_recent(),
            reason=pick(STANDALONE_WARNING_REASONS),
        )

    # --- fast-track citizen: exactly one linked warning --------------------
    fasttrack_pool = [c for c in invalid_owners if c != count_ban_citizen]
    fasttrack_citizen = None
    if fasttrack_pool:
        fasttrack_citizen = pick(fasttrack_pool)
        info = pick(invalid_by_owner[fasttrack_citizen])
        issue_warning(fasttrack_citizen, at=_after(info.end_at), report_info=info)
        progress.detail(
            f"Warned {fasttrack_citizen.user_number} "
            f"(linked: {info.report.report_number})"
        )

    # --- fill the remaining quota with standalone warnings -----------------
    already = {count_ban_citizen, fasttrack_citizen} - {None}
    fillable = [c for c in active_citizens if c not in already]
    per_citizen_quota = defaultdict(int)
    while created_warnings < warning_count_target and fillable:
        citizen = pick(fillable)
        per_citizen_quota[citizen] += 1
        # Keep fill citizens below the ban threshold so the moderation
        # outcome stays intentional (only the designated citizen is banned).
        if per_citizen_quota[citizen] >= BAN_WARNING_THRESHOLD - 1:
            fillable.remove(citizen)
        at = _recent()
        issue_warning(citizen, at=at, reason=pick(STANDALONE_WARNING_REASONS))
    if created_warnings:
        progress.step(f"Issued {created_warnings} citizen warnings")

    # --- bans --------------------------------------------------------------
    if count_ban_citizen is not None:
        ban_at = _after(_last_warning_at(count_ban_citizen)) + timedelta(hours=6)
        ban(
            count_ban_citizen,
            at=_clamp(ban_at),
            reason=pick(BAN_REASONS),
        )
        progress.step(
            f"Banned {count_ban_citizen.user_number} "
            f"({BAN_WARNING_THRESHOLD}+ warnings, count path)"
        )

    if fasttrack_citizen is not None:
        linked_info = pick(invalid_by_owner[fasttrack_citizen])
        ban_at = _after(_last_warning_at(fasttrack_citizen)) + timedelta(hours=4)
        fasttrack_ban_at = _clamp(ban_at)
        ban(
            fasttrack_citizen,
            at=fasttrack_ban_at,
            reason=pick(BAN_REASONS),
            fast_track_report_number=linked_info.report.report_number,
        )
        unban_candidates.append((fasttrack_citizen, fasttrack_ban_at))
        progress.step(
            f"Banned {fasttrack_citizen.user_number} "
            f"(fast-track: {linked_info.report.report_number})"
        )

    # --- unban one citizen to cover the unbanned state ---------------------
    unbanned = 0
    if unban_candidates:
        citizen, banned_at = pick(unban_candidates)
        actor = pick(warn_actors)
        citizen.is_active = True
        citizen.save(update_fields=["is_active"])
        unbanned = 1
        reason = pick(UNBAN_REASONS)
        # The unban must always follow its ban in the audit trail, even when
        # the ban timestamp was clamped close to now.
        unban_at = banned_at + timedelta(hours=random.randint(2, 48))
        ceiling = timezone.now() - timedelta(minutes=30)
        if unban_at > ceiling:
            unban_at = banned_at + timedelta(minutes=30)
        if unban_at > ceiling:
            unban_at = ceiling
        events.add(AuditEvent(
            occurred_at=unban_at,
            action="UNBAN",
            module="USER",
            actor=actor,
            target=citizen,
            description=(
                f"{citizen.user_number} ({citizen.role.role_name}) was unbanned "
                f"by {actor.user_number} with the reason: \"{reason}\""
            ),
            payload={"reason": reason},
        ))
        progress.step(f"Unbanned {citizen.user_number}")

    stats = {
        "warnings": created_warnings,
        "banned": len(banned_users) - unbanned,
        "unbanned": unbanned,
    }
    progress.done(
        f"{stats['warnings']} warnings, {stats['banned']} banned, "
        f"{stats['unbanned']} unbanned"
    )
    return stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _warning_reason(report_info: ReportSeedInfo | None) -> str:
    if report_info is not None and chance(0.6):
        return (
            "Report was flagged as invalid by verification and matches "
            "previous prank submissions."
        )
    return pick([
        "Repeatedly submitted hoax hazard reports that could not be "
        "verified on site.",
        "Submitted a misleading photo unrelated to the reported location.",
        "Deliberately altered report details after staff reached out for "
        "clarification.",
    ])


def _after(timestamp):
    return _clamp(timestamp + timedelta(hours=random.randint(2, 36)))


def _recent():
    return _clamp(timezone.now() - timedelta(days=random.randint(1, 10)))


def _clamp(timestamp):
    ceiling = timezone.now() - timedelta(hours=1)
    return min(timestamp, ceiling)


def _last_warning_at(citizen):
    latest = (
        CitizenWarnings.objects.filter(user=citizen)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    return latest or timezone.now() - timedelta(days=2)
