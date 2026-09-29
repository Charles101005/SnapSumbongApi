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
            description = f"{module.value} {target_identifier} was created by {user.user_number}"

        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.CREATE,
            module=module,
            description=description,
            payload=payload,
            target_object=target_object
        )

    @staticmethod
    def log_update(
            *,
            user: Users,
            module: AuditLogs.ModuleType,
            target_object: Users|Roles,
            description: str,
            payload: dict[str, Any]|None=None,
    ) -> None:

        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.UPDATE,
            module=module,
            description=description,
            payload=payload,
            target_object=target_object
        )

    @staticmethod
    def log_deactivate(
            *,
            user: Users,
            module: AuditLogs.ModuleType,
            deactivated_user: Users,
            reason: str,
            payload_override: dict[str, Any]|None=None,
            description_override: str|None=None,
    ) -> None:
        description = description_override
        payload = payload_override

        deactivated_user_number = deactivated_user.user_number
        deactivated_user_role_name = deactivated_user.role.role_name

        if not description:
            description = (
                f"{deactivated_user_number} ({deactivated_user_role_name}) was deactivated by {user.user_number}"
            ) + f" with the reason: \"{reason}\""

        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.DEACTIVATE,
            module=module,
            description=description,
            payload=payload,
            target_object=deactivated_user
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

        if isinstance(remarks, str):
            remarks = remarks.strip()

        if not payload:
            payload = {
                "status_change": {"from": old_status, "to": new_status},
                "remarks": remarks,
            }

        if not description:
            actor = user.user_number if user else 'System'
            description_remarks = f" with the remarks: \"{remarks}\"" if remarks else ""

            old_status = old_status.upper()
            new_status = new_status.upper()
            description = (
                f"REPORT {report.report_number} status was changed from {old_status} to {new_status} by {actor}"
            ) + description_remarks

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
            payload_override: dict[str, Any]|None=None,
            description_override: str|None=None
    ) -> None:
        payload = payload_override
        description = description_override

        if not payload:
            payload = {
                "severity_change": {"from": old_severity, "to": new_severity},
            }

        if not description:
            actor = user.user_number

            description = (
                f"REPORT {report.report_number} severity was changed from {old_severity} to {new_severity} by {actor}"
            )

        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.SEVERITY_CHANGE,
            module=AuditLogs.ModuleType.REPORT,
            description=description,
            payload=payload,
            target_object=report
        )
