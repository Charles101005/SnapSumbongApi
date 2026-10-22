from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import api_view

from shared.authorization import AllPermissions
from shared.authorization.decorators import require_any_perms
from shared.authorization.service import AuthorizationService
from apps.audits.models import AuditLogs


@api_view(['GET'])
@require_any_perms(
    AllPermissions.AUDITS.READ_SYSTEM_LOGS,
    AllPermissions.AUDITS.READ_REPORT_LOGS,
)
def lookup_audit_log_modules_view(request: Request) -> Response:
    # Mirror _authorized_audit_logs: only offer the module choices the
    # requester's audit permissions actually unlock, so the filter UI
    # never advertises rows the list endpoint would refuse to return.
    modules = []
    if AuthorizationService.has_perm(request.user, AllPermissions.AUDITS.READ_SYSTEM_LOGS):
        modules.extend(AuditLogs.ModuleType.get_system_modules())
    if AuthorizationService.has_perm(request.user, AllPermissions.AUDITS.READ_REPORT_LOGS):
        modules.extend(AuditLogs.ModuleType.get_report_modules())

    result = [
        {
            "value": module.value,
            "label": module.label,
        }
        for module in modules
    ]

    return Response(data=result, status=status.HTTP_200_OK)
