from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status

from apps.reports.services import ReportService, HazardCategoryService
from apps.reports.serializers.response.lookup_serializer import LookupFilterCitizenReportResponseSerializer


@api_view(["GET"])
def lookup_filter_citizen_report_view(request: Request):
    lookup_filters = {
        "categories": HazardCategoryService.get_all_category().value,
        "statuses": ReportService.get_status_list().value,
        "severities": ReportService.get_severity_list().value
    }

    data = LookupFilterCitizenReportResponseSerializer(
        lookup_filters,
        context={"user": request.user}
    ).data

    return Response(data=data, status=status.HTTP_200_OK)




