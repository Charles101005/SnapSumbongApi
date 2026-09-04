from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status

from apps.reports.services import ReportService
from shared.results import DomainResultResponse
from shared.views import BrowsableJSONViewMixin
from apps.reports.serializers.request.report_serializer import (
    ReportImageSignatureRequestSerializer,
    CreateReportRequestSerializer
)
from apps.reports.serializers.response.report_serializer import (
    ReportImageSignatureResponseSerializer,
    CreateReportResponseSerializer
)


class ReportImageSignatureView(APIView, BrowsableJSONViewMixin):
    serializer_class = ReportImageSignatureRequestSerializer

    def get(self, request: Request) -> Response:
        serializer = ReportImageSignatureRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = ReportService.get_hazard_image_upload_credentials(validated_data["image_count"])

        return DomainResultResponse(result).respond(
            serializer_class=ReportImageSignatureResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )


class ReportListView(APIView, BrowsableJSONViewMixin):
    def get(self, request: Request) -> Response:
        pass

    def post(self, request: Request) -> Response:
        serializer = CreateReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = ReportService.create_assign_hazard_report(
            reported_by_id=request.user.user_id,
            category_ids=validated_data["category_ids"],
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


class ReportDetailView(APIView, BrowsableJSONViewMixin):
    def get(self, request: Request, report_number: str) -> Response:
        pass

    def put(self, request: Request, report_number: str) -> Response:
        pass