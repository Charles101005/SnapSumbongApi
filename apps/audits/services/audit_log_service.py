from typing import Any

from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports
from apps.accounts.models import Users, Roles


class AuditLogService:
    @staticmethod
    def _log(
            *,
            user_id: int|None,
            action: AuditLogs.ActionType,
            module: AuditLogs.ModuleType,
            description: str,
            payload: dict[str, Any]|None=None,
            target_object: HazardReports|Users|Roles
    ) -> None:
        AuditLogs.objects.create(
            user_id=user_id,
            action=action,
            module=module,
            description=description,
            payload=payload if payload else {},
            target_object=target_object
        )

    @staticmethod
    def log_create(
            *,
            user: Users,
            module: AuditLogs.ModuleType,
            payload: dict[str, Any]|None=None,
            target_object: HazardReports|Users|Roles,
            description: str|None=None
    ) -> None:
        if not description:
            description = f"\"{user.email}\" created {module.value} ID({target_object.pk})"

        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.CREATE,
            module=module,
            description=description,
            payload=payload,
            target_object=target_object
        )

    @staticmethod
    def log_report_status_change(
            *,
            user: Users|None=None,
            old_status: str,
            payload: dict[str, Any]|None=None,
            report: HazardReports,
            description: str|None=None
    ) -> None:
        if not description:
            actor = user.email if user else 'System'

            description = (
                f"\"{actor}\" updated REPORT ({report.report_number}) status from {old_status} to {report.status}"
            )

        AuditLogService._log(
            user_id=user.user_id if user else None,
            action=AuditLogs.ActionType.STATUS_CHANGE,
            module=AuditLogs.ModuleType.REPORT,
            description=description,
            payload=payload,
            target_object=report
        )
