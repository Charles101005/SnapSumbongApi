from django.db.models import Count

from apps.accounts.models import Users
from apps.reports.models import HazardReports
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

        queryset = queryset.values("status").annotate(count=Count("report_id"))

        metrics = {
            "total_count": queryset.count(),
            "count_by_status": {item["status"].lower(): item["count"] for item in queryset},
        }

        return DomainResult.success(metrics)
