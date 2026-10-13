from django.db.models import Count, Q, QuerySet

from apps.accounts.models import Users
from apps.accounts.domain_errors.user_error import UserNotFoundError
from apps.reports.models import HazardReports, ReportImages
from apps.analytics.domain_errors.analytic_error import MetricsNotApplicableToRoleError
from shared.results import DomainResult
from shared.authorization import AllPermissions
from shared.authorization.service import AuthorizationService


# DO 47 s.2024-aligned compliance weights: SLA adherence dominates, with
# photolog completeness and independent validation making up the remainder.
_COMPLIANCE_WEIGHTS = {
    "sla_on_time": 60.0,
    "photolog_completeness": 25.0,
    "validation_independence": 15.0,
}


def _rating_for(score: float | None) -> str:
    if score is None:
        return "No Data"
    if score >= 90:
        return "Outstanding"
    if score >= 80:
        return "Very Satisfactory"
    if score >= 70:
        return "Satisfactory"
    if score >= 60:
        return "Unsatisfactory"
    return "Poor"


def _handler_display_name(user: Users) -> str:
    middle_name = f" {user.middle_name[0].upper()}." if user.middle_name else ""
    return f"{user.last_name}, {user.first_name}{middle_name}"


class AnalyticService:
    @staticmethod
    def get_authorized_report_metrics(user: Users) -> DomainResult[dict[str, int]]:
        if AuthorizationService.has_perm(user, AllPermissions.ANALYTICS.READ_ALL_METRICS):
            queryset = HazardReports.objects.all()

        elif AuthorizationService.has_perm(user, AllPermissions.ANALYTICS.READ_ASSIGNED_METRICS):
            queryset = HazardReports.objects.filter(assigned_to_id=user.user_id)

        else:
            queryset = HazardReports.objects.filter(reported_by_id=user.user_id)

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
    def get_handler_compliance_metrics() -> DomainResult[dict]:
        """DO 47-aligned per-handler compliance score (0-100 + adjectival).

        Scored only on phase-4 (Resolved/Closed) reports assigned to a staff
        handler: SLA on-time % (weight 60), photolog completeness % (weight
        25), independent validation % (weight 15). Components without a
        denominator are dropped and the remaining weights renormalized, so
        legacy rows predating due_at or the photolog still score fairly.
        """
        reports = (
            HazardReports.objects.filter(
                status__in=[HazardReports.Status.RESOLVED, HazardReports.Status.CLOSED],
                assigned_to_id__isnull=False,
            )
            .select_related("assigned_to")
            .prefetch_related("images")
        )

        handlers: dict[int, dict] = {}
        for report in reports:
            handler = report.assigned_to
            stats = handlers.setdefault(report.assigned_to_id, {
                "user_number": handler.user_number,
                "handler_name": _handler_display_name(handler),
                "resolved_count": 0,
                "sla_total": 0,
                "sla_on_time": 0,
                "photolog_total": 0,
                "photolog_ok": 0,
                "validation_total": 0,
                "validation_ok": 0,
            })
            stats["resolved_count"] += 1

            if report.due_at is not None:
                stats["sla_total"] += 1
                if report.resolved_at is not None and report.resolved_at <= report.due_at:
                    stats["sla_on_time"] += 1

            stats["photolog_total"] += 1
            photo_types = {image.photo_type for image in report.images.all()}
            if {ReportImages.PhotoType.DURING, ReportImages.PhotoType.AFTER} <= photo_types:
                stats["photolog_ok"] += 1

            stats["validation_total"] += 1
            if (
                report.validated_by_id is not None
                and report.validated_by_id != report.assigned_to_id
            ):
                stats["validation_ok"] += 1

        def _pct(ok: int, total: int) -> float | None:
            if not total:
                return None
            return round(ok / total * 100, 1)

        results = []
        for stats in handlers.values():
            sla_pct = _pct(stats["sla_on_time"], stats["sla_total"])
            photolog_pct = _pct(stats["photolog_ok"], stats["photolog_total"])
            validation_pct = _pct(stats["validation_ok"], stats["validation_total"])

            components = {
                "sla_on_time": sla_pct,
                "photolog_completeness": photolog_pct,
                "validation_independence": validation_pct,
            }
            available = {key: value for key, value in components.items() if value is not None}
            if available:
                total_weight = sum(_COMPLIANCE_WEIGHTS[key] for key in available)
                score = round(
                    sum(value * _COMPLIANCE_WEIGHTS[key] for key, value in available.items())
                    / total_weight,
                    1,
                )
            else:
                score = None

            results.append({
                "user_number": stats["user_number"],
                "handler_name": stats["handler_name"],
                "resolved_count": stats["resolved_count"],
                "sla_on_time_pct": sla_pct,
                "photolog_pct": photolog_pct,
                "validation_pct": validation_pct,
                "score": score,
                "rating": _rating_for(score),
            })

        # Rank: highest score first, unrated handlers last.
        results.sort(
            key=lambda item: (item["score"] is None, -(item["score"] or 0), item["handler_name"]),
        )

        return DomainResult.success({
            "weights": dict(_COMPLIANCE_WEIGHTS),
            "handlers": results,
        })
