from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.results import DomainResultResponse
from shared.authorization import AllPermissions
from shared.authorization.decorators import require_any_perms
from shared.pagination import SmallListPagination
from apps.audits.services import AuditLogService
from apps.audits.serializers.request.audit_log_serializer import ListAuditLogRequestSerializer
from apps.audits.serializers.response.audit_log_serializer import (
    ListAuditLogResponseSerializer,
    DetailAuditLogResponseSerializer
)


class AuditLogListView(APIView):
    @require_any_perms(
        AllPermissions.AUDITS.READ_SYSTEM_LOGS,
        AllPermissions.AUDITS.READ_REPORT_LOGS,
    )
    def get(self, request: Request) -> Response:
        serializer = ListAuditLogRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = AuditLogService.list_authorized_audit_logs(
            user=request.user,
            query_filters=validated_data
        )

        return DomainResultResponse(result).respond_with_pagination(
            request=request,
            pagination_class=SmallListPagination,
            serializer_class=ListAuditLogResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )


class AuditLogDetailView(APIView):
    @require_any_perms(
        AllPermissions.AUDITS.READ_SYSTEM_LOGS,
        AllPermissions.AUDITS.READ_REPORT_LOGS,
    )
    def get(self, request: Request, audit_log_number: str) -> Response:
        result = AuditLogService.get_authorized_audit_log(
            user=request.user,
            audit_log_number=audit_log_number,
        )

        return DomainResultResponse(result).respond(
            serializer_class=DetailAuditLogResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )
