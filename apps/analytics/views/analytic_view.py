from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from apps.analytics.services import AnalyticService
from shared.results import DomainResultResponse
from apps.analytics.serializers.response.analytic_serializer import GetReportMetricsResponseSerializer


@api_view(["GET"])
def hazard_report_metrics_view(request: Request) -> Response:
    result = AnalyticService.get_authorized_report_metrics(request.user)

    return DomainResultResponse(result).respond(
        serializer_class=GetReportMetricsResponseSerializer,
        success_status_code=status.HTTP_200_OK,
    )


