from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from apps.analytics.services import AnalyticService
from shared.results import DomainResultResponse
from shared.authorization.decorators import require_perm, require_any_perms
from shared.ratelimit import rate_limit, StandardRateLimit
from shared.authorization import AllPermissions
from apps.analytics.serializers.response.analytic_serializer import (
    GetReportMetricsResponseSerializer,
    GetHandlerWorkloadResponseSerializer,
    GetOverviewResponseSerializer,
)


def _range_params(request: Request) -> dict:
    return {
        "from_date": request.query_params.get("from"),
        "to_date": request.query_params.get("to"),
    }


@api_view(["GET"])
@rate_limit(StandardRateLimit)
@require_any_perms(
    AllPermissions.ANALYTICS.READ_ALL_METRICS,
    AllPermissions.ANALYTICS.READ_ASSIGNED_METRICS,
    AllPermissions.ANALYTICS.READ_OWN_METRICS,
)
def hazard_report_metrics_view(request: Request) -> Response:
    result = AnalyticService.get_authorized_report_metrics(request.user)

    return DomainResultResponse(result).respond(
        serializer_class=GetReportMetricsResponseSerializer,
        success_status_code=status.HTTP_200_OK,
    )

@api_view(["GET"])
@rate_limit(StandardRateLimit)
@require_any_perms(
    AllPermissions.ANALYTICS.READ_ALL_METRICS,
    AllPermissions.ANALYTICS.READ_ASSIGNED_METRICS,
    AllPermissions.ANALYTICS.READ_OWN_METRICS,
)
def handler_overview_view(request: Request) -> Response:
    result = AnalyticService.get_report_overview(
        user=request.user,
        **_range_params(request),
    )

    return DomainResultResponse(result).respond(
        serializer_class=GetOverviewResponseSerializer,
        success_status_code=status.HTTP_200_OK,
    )

@api_view(["GET"])
@rate_limit(StandardRateLimit)
@require_perm(AllPermissions.ANALYTICS.READ_HANDLER_PERFORMANCE)
def employee_metrics_view(request: Request, user_number: str) -> Response:
    result = AnalyticService.get_user_activity_metrics(
        user_number=user_number,
        is_staff=True,
    )

    return DomainResultResponse(result).respond(
        success_status_code=status.HTTP_200_OK,
    )

@api_view(["GET"])
@rate_limit(StandardRateLimit)
@require_perm(AllPermissions.USERS.READ_ALL)
def citizen_metrics_view(request: Request, user_number: str) -> Response:
    result = AnalyticService.get_user_activity_metrics(
        user_number=user_number,
        is_staff=False,
    )

    return DomainResultResponse(result).respond(
        success_status_code=status.HTTP_200_OK,
    )


@api_view(["GET"])
@rate_limit(StandardRateLimit)
@require_any_perms(
    AllPermissions.ANALYTICS.READ_ALL_METRICS,
    AllPermissions.ANALYTICS.READ_ASSIGNED_METRICS,
    AllPermissions.ANALYTICS.READ_OWN_METRICS,
)
def handler_workload_view(request: Request) -> Response:
    result = AnalyticService.get_handler_workload(
        user=request.user,
        **_range_params(request),
    )

    return DomainResultResponse(result).respond(
        serializer_class=GetHandlerWorkloadResponseSerializer,
        success_status_code=status.HTTP_200_OK,
    )
