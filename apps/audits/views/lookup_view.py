from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import api_view

from shared.authorization import AllPermissions
from shared.authorization.decorators import require_any_perms
from apps.audits.services import AuditLogService


@api_view(['GET'])
@require_any_perms(
    AllPermissions.AUDITS.READ_SYSTEM_LOGS,
    AllPermissions.AUDITS.READ_REPORT_LOGS,
)
def lookup_audit_log_modules_view(request: Request) -> Response:
    result = [
        {
            "value": value,
            "label": label,
        }
        for value, label in AuditLogService.ModuleType.choices
    ]

    return Response(data=result, status=status.HTTP_200_OK)
