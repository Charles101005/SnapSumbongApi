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
            target_identifier: int|str,
            description_override: str|None=None
    ) -> None:
        description = description_override

        if not description:
            description = f"\"{user.email}\" created {module.value} ID({target_identifier})"

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
            user: Users|None,
            old_status: str,
            new_status: str,
            remarks: str|None=None,
            report: HazardReports,
            payload_override: dict[str, Any]|None=None,
            description_override: str|None=None
    ) -> None:
        payload = payload_override
        description = description_override

        if not payload:
            if isinstance(remarks, str):
                remarks = remarks.strip()

            payload = {
                "status_change": {"from": old_status, "to": new_status},
                "remarks": remarks,
            }

        if not description:
            actor = user.email if user else 'System'

            old_status = old_status.upper()
            new_status = new_status.upper()
            description = (
                f"\"{actor}\" updated REPORT ({report.report_number}) status from {old_status} to {new_status}"
            )

        AuditLogService._log(
            user_id=user.user_id if user else None,
            action=AuditLogs.ActionType.STATUS_CHANGE,
            module=AuditLogs.ModuleType.REPORT,
            description=description,
            payload=payload,
            target_object=report
        )

    @staticmethod
    def log_report_severity_change(
            *,
            user: Users,
            old_severity: str,
            new_severity: str,
            report: HazardReports,
            payload_override: dict[str, Any] | None = None,
            description_override: str | None = None
    ) -> None:
        payload = payload_override
        description = description_override

        if not payload:
            payload = {
                "severity_change": {"from": old_severity, "to": new_severity},
            }

        if not description:
            actor = user.email

            description = (
                f"\"{actor}\" updated REPORT ({report.report_number}) severity from {old_severity} to {new_severity}"
            )

        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.SEVERITY_CHANGE,
            module=AuditLogs.ModuleType.REPORT,
            description=description,
            payload=payload,
            target_object=report
        )
