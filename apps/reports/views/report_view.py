from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status

from apps.reports.services import ReportService
from shared.results import DomainResultResponse
from shared.authorization.decorators import require_perm, require_any_perms
from shared.authorization import AllPermissions
from shared.pagination import SmallListPagination
from apps.reports.serializers.request.report_serializer import (
    ReportImageSignatureRequestSerializer,
    CreateReportRequestSerializer,
    GetReportListRequestSerializer
)
from apps.reports.serializers.response.report_serializer import (
    ReportImageSignatureResponseSerializer,
    CreateReportResponseSerializer,
    GetReportListResponseSerializer,
    GetReportDetailResponseSerializer
)


class ReportImageSignatureView(APIView):
    def get(self, request: Request) -> Response:
        serializer = ReportImageSignatureRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = ReportService.get_hazard_image_upload_credentials(validated_data["image_count"])

        return DomainResultResponse(result).respond(
            serializer_class=ReportImageSignatureResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )


class ReportListView(APIView):
    @require_any_perms(
        AllPermissions.REPORTS.READ_ALL,
        AllPermissions.REPORTS.READ_ASSIGNED,
        AllPermissions.REPORTS.READ_OWN,
    )
    def get(self, request: Request) -> Response:
        serializer = GetReportListRequestSerializer(
            data=request.query_params,
            context={"user": request.user}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = ReportService.list_authorized_reports(user=request.user, query_filters=validated_data)

        return DomainResultResponse(result).respond_with_pagination(
            request=request,
            pagination_class=SmallListPagination,
            serializer_class=GetReportListResponseSerializer,
            serializer_context={"user": request.user},
            success_status_code=status.HTTP_200_OK
        )

    @require_perm(AllPermissions.REPORTS.CREATE)
    def post(self, request: Request) -> Response:
        serializer = CreateReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = ReportService.create_assign_hazard_report(
            reported_by_id=request.user.user_id,
            category_id=validated_data["category_id"],
            latitude=validated_data["latitude"],
            longitude=validated_data["longitude"],
            address=validated_data["address"],
            description=validated_data["description"],
            is_anonymous=validated_data["is_anonymous"],
            image_urls=validated_data["image_urls"],
        )

        return DomainResultResponse(result).respond(
            serializer_class=CreateReportResponseSerializer,
            success_status_code=status.HTTP_201_CREATED,
        )


class ReportDetailView(APIView):
    @require_any_perms(
        AllPermissions.REPORTS.READ_ALL,
        AllPermissions.REPORTS.READ_ASSIGNED,
        AllPermissions.REPORTS.READ_OWN,
    )
    def get(self, request: Request, report_number: str) -> Response:
        result = ReportService.get_authorized_reports(user=request.user, report_number=report_number)

        return DomainResultResponse(result).respond(
            serializer_class=GetReportDetailResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )

    def put(self, request: Request, report_number: str) -> Response:
        pass