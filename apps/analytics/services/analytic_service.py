from django.db.models import Count, Q, QuerySet

from apps.accounts.models import Users
from apps.accounts.domain_errors.user_error import UserNotFoundError
from apps.reports.models import HazardReports
from apps.analytics.domain_errors.analytic_error import MetricsNotApplicableToRoleError
from shared.results import DomainResult
from shared.authorization import AllPermissions
from shared.authorization.service import AuthorizationService


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
