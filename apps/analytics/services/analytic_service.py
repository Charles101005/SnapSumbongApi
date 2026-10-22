from datetime import date as _date
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Max, Min, Q, QuerySet
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import Users
from apps.accounts.domain_errors.user_error import UserNotFoundError
from apps.reports.models import HazardReports
from apps.analytics.domain_errors.analytic_error import (
    InvalidAnalyticsRangeError,
    MetricsNotApplicableToRoleError,
)
from shared.results import DomainResult
from shared.authorization import AllPermissions
from shared.authorization.service import AuthorizationService


def _round1(value: float) -> float:
    return round(value, 1)


# Parses the optional ?from=/&to= range shared by the overview and
# handler workload endpoints. Values arrive as YYYY-MM-DD strings ("" or
# absent = unbounded). Anything unparsable or backwards is a client error.
def _parse_range(from_date, to_date) -> tuple[_date | None, _date | None] | None:
    def _coerce(value):
        if value in (None, ""):
            return None
        if isinstance(value, _date):
            return value
        return _date.fromisoformat(str(value))

    try:
        start = _coerce(from_date)
        end = _coerce(to_date)
    except ValueError:
        return None

    if start and end and start > end:
        return None

    return start, end


def _apply_date_bounds(queryset: QuerySet, field: str, start, end) -> QuerySet:
    if start is not None:
        queryset = queryset.filter(**{f"{field}__date__gte": start})
    if end is not None:
        queryset = queryset.filter(**{f"{field}__date__lte": end})
    return queryset


class AnalyticService:
    @staticmethod
    def _scoped_reports(user: Users) -> QuerySet[HazardReports]:
        if AuthorizationService.has_perm(user, AllPermissions.ANALYTICS.READ_ALL_METRICS):
            return HazardReports.objects.all()

        if AuthorizationService.has_perm(user, AllPermissions.ANALYTICS.READ_ASSIGNED_METRICS):
            return HazardReports.objects.filter(assigned_to_id=user.user_id)

        return HazardReports.objects.filter(reported_by_id=user.user_id)

    @staticmethod
    def get_authorized_report_metrics(user: Users) -> DomainResult[dict[str, int]]:
        queryset = AnalyticService._scoped_reports(user)

        total_count = queryset.count()
        queryset = queryset.values("status").annotate(count=Count("report_id"))

        metrics = {
            "total_count": total_count,
            "count_by_status": {item["status"].lower(): item["count"] for item in queryset},
        }

        return DomainResult.success(metrics)

    @staticmethod
    def get_user_activity_metrics(
            *,
            user_number: str,
            is_staff: bool,
    ) -> DomainResult[dict[str, int]]:
        user = Users.objects.filter(
            user_number__iexact=user_number,
            is_staff=is_staff
        ).first()

        if user is None:
            return DomainResult.error(UserNotFoundError)


        if is_staff and not AuthorizationService.has_perm(user, AllPermissions.REPORTS.UPDATE_ASSIGNED):
            return DomainResult.error(MetricsNotApplicableToRoleError)

        field = "assigned_to_id" if is_staff else "reported_by_id"
        queryset = HazardReports.objects.filter(**{field: user.user_id})

        metrics = queryset.aggregate(
            total=Count("report_id"),
            resolved_count=Count("report_id", filter=Q(status=HazardReports.Status.RESOLVED))
        )

        activity_metrics = {
            f"total_reports_{'handled' if is_staff else 'submitted'}": metrics["total"],
            "total_reports_resolved": metrics["resolved_count"] or 0,
        }

        return DomainResult.success(activity_metrics)

    @staticmethod
    def get_report_overview(
            *,
            user: Users,
            from_date=None,
            to_date=None,
    ) -> DomainResult[dict]:
        """Period aggregates for the Analytics page, in four lenses.

        - intake:  reports CREATED in the range (volume, severity, status mix,
                   daily series, span for chart bounds)
        - delivery: reports RESOLVED in the range (avg time, weekly trend,
                   slowest) — "work completed this period"
        - sla:     reports whose DUE DATE falls in the range, judged by
                   outcome: on_time / late / still-open breach / pending.
                   Judged outcomes never change retroactively; a report that
                   missed its deadline counts as a failure whether it was
                   later resolved late or is still open.
        - live:    unscoped as-of-now backlog (open + overdue), matching the
                   Operations summary bar's semantics.

        Computed as DB aggregates/one-pass iteration server-side so the page
        never depends on paginated report rows.
        """
        parsed = _parse_range(from_date, to_date)
        if parsed is None:
            return DomainResult.error(InvalidAnalyticsRangeError)
        start, end = parsed

        now = timezone.now()
        compliance_since = settings.DO47_COMPLIANCE_SINCE
        scoped = AnalyticService._scoped_reports(user)

        # ---- intake -----------------------------------------------------
        intake_qs = _apply_date_bounds(scoped, "created_at", start, end)

        by_severity = {level.value: 0 for level in HazardReports.Severity}
        by_severity["unknown"] = 0
        for row in intake_qs.values("severity").annotate(count=Count("report_id")):
            key = (row["severity"] or "").upper()
            if key in by_severity:
                by_severity[key] = row["count"]
            else:
                by_severity["unknown"] += row["count"]

        by_status = {status.value.lower(): 0 for status in HazardReports.Status}
        for row in intake_qs.values("status").annotate(count=Count("report_id")):
            by_status[row["status"].lower()] = row["count"]

        daily = [
            {"date": row["day"].isoformat(), "count": row["count"]}
            for row in (
                intake_qs
                .annotate(day=TruncDate("created_at"))
                .values("day")
                .annotate(count=Count("report_id"))
                .order_by("day")
            )
        ]

        span_bounds = intake_qs.aggregate(
            min_day=Min("created_at__date"),
            max_day=Max("created_at__date"),
        )
        span = {
            "from": span_bounds["min_day"].isoformat() if span_bounds["min_day"] else "",
            "to": span_bounds["max_day"].isoformat() if span_bounds["max_day"] else "",
        }

        # ---- delivery ---------------------------------------------------
        delivery_qs = _apply_date_bounds(
            scoped.filter(resolved_at__isnull=False), "resolved_at", start, end
        )

        durations: list[float] = []
        daily_buckets: dict[str, dict[str, float | int]] = {}
        weekly: dict[str, dict[str, float | int]] = {}
        slowest: list[dict] = []
        for _report_number, created_at, resolved_at, category_name in (
            delivery_qs
            .select_related("category")
            .values_list("report_number", "created_at", "resolved_at", "category__hazard_name")
        ):
            if created_at is None:
                continue
            days = (resolved_at - created_at).total_seconds() / 86400
            durations.append(days)

            resolved_day = timezone.localdate(resolved_at)
            day_group = daily_buckets.setdefault(resolved_day.isoformat(), {"sum": 0.0, "resolved": 0})
            day_group["sum"] += days
            day_group["resolved"] += 1
            week_start = resolved_day - timedelta(days=resolved_day.weekday())
            week_group = weekly.setdefault(week_start.isoformat(), {"sum": 0.0, "resolved": 0})
            week_group["sum"] += days
            week_group["resolved"] += 1

            slowest.append({
                "report_number": _report_number,
                "category": category_name,
                "resolved_at": resolved_at,
                "days": _round1(days),
            })

        def _trend(bucket: dict[str, dict[str, float | int]], key_name: str) -> list[dict]:
            return [
                {
                    key_name: bucket_key,
                    "avg_days": _round1(group["sum"] / group["resolved"]),
                    "resolved": group["resolved"],
                }
                for bucket_key, group in sorted(bucket.items())
            ]

        delivery = {
            "resolved": len(durations),
            "avg_days": _round1(sum(durations) / len(durations)) if durations else None,
            "daily": _trend(daily_buckets, "date"),
            "weekly": _trend(weekly, "week_start"),
            "slowest": sorted(slowest, key=lambda item: item["days"], reverse=True)[:5],
        }

        # ---- SLA outcomes (due cohort) ---------------------------------
        sla_qs = _apply_date_bounds(
            scoped.filter(due_at__isnull=False), "due_at", start, end
        )

        on_time = late = breach = pending = 0
        for created_at, due_at, resolved_at, status_value in sla_qs.values_list(
            "created_at", "due_at", "resolved_at", "status"
        ):
            if compliance_since is not None and timezone.localdate(created_at) < compliance_since:
                continue

            if resolved_at is not None:
                if resolved_at <= due_at:
                    on_time += 1
                else:
                    late += 1
            elif HazardReports.Status(status_value).phase < 4:
                if due_at <= now:
                    breach += 1
                else:
                    pending += 1
            # Phase-4 rows that never resolved (Invalid / force-closed /
            # referral closures) are not judgeable on response time.

        judged = on_time + late + breach
        sla = {
            "on_time": on_time,
            "late": late,
            "breach": breach,
            "pending": pending,
            "judged": judged,
            "on_time_pct": _round1(on_time / judged * 100) if judged else None,
        }

        # ---- live backlog (unscoped) -----------------------------------
        open_statuses = [status.value for status in HazardReports.Status if status.phase < 4]
        live = {
            "open": scoped.filter(status__in=open_statuses).count(),
            "overdue": scoped.filter(
                status__in=open_statuses,
                due_at__isnull=False,
                due_at__lt=now,
            ).count(),
        }

        return DomainResult.success({
            "range": {
                "from": start.isoformat() if start else "",
                "to": end.isoformat() if end else "",
            },
            "span": span,
            "intake": {
                "total": intake_qs.count(),
                "by_severity": by_severity,
                "by_status": by_status,
                "daily": daily,
            },
            "delivery": delivery,
            "sla": sla,
            "live": live,
        })

    @staticmethod
    def get_handler_workload(
            *, user: Users, from_date=None, to_date=None,
    ) -> DomainResult[dict]:
        """Per-handler workload over reports due in the requested range.

        Due-cohort lens: every report whose DO 47 deadline falls in the
        range (all-time when no range is given) and has an assignee is
        counted once — no outcome filtering, no scoring:

        - handled  = attributed to this handler (the current custodian;
                     transfers only happen before phase 4)
        - resolved = of those, how many carry a resolved_at

        Scoped to the viewer's report-read permissions exactly like the
        overview, and sorted alphabetically — the table describes the
        team, it does not rank it.
        """
        parsed = _parse_range(from_date, to_date)
        if parsed is None:
            return DomainResult.error(InvalidAnalyticsRangeError)
        start, end = parsed

        reports = _apply_date_bounds(
            AnalyticService._scoped_reports(user).filter(
                due_at__isnull=False,
                assigned_to_id__isnull=False,
            ),
            "due_at",
            start,
            end,
        )

        handlers: dict[str, dict] = {}
        rows = reports.values_list(
            "resolved_at",
            "assigned_to__user_number",
            "assigned_to__first_name",
            "assigned_to__middle_name",
            "assigned_to__last_name",
        )
        for resolved_at, user_number, first_name, middle_name, last_name in rows:
            stats = handlers.get(user_number)
            if stats is None:
                middle = f" {middle_name[0].upper()}." if middle_name else ""
                stats = handlers[user_number] = {
                    "user_number": user_number,
                    "handler_name": f"{last_name}, {first_name}{middle}",
                    "handled": 0,
                    "resolved": 0,
                }
            stats["handled"] += 1
            if resolved_at is not None:
                stats["resolved"] += 1

        results = sorted(handlers.values(), key=lambda item: item["handler_name"])

        return DomainResult.success({"handlers": results})
