from typing import Any

from django.db.models import Q

from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports
from apps.accounts.models import Users, Roles
from apps.audits.exceptions.audit_log_exception import AuditLogNotFoundException
from shared.results import DomainResult
from shared.authorization import AllPermissions
from shared.authorization.service import AuthorizationService


class AuditLogService:
    ActionType = AuditLogs.ActionType
    ModuleType = AuditLogs.ModuleType

    @staticmethod
    def _log(
            *,
            actor_id: int|None,
            action: AuditLogs.ActionType,
            module: AuditLogs.ModuleType,
            description: str,
            payload: dict[str, Any]|None=None,
            target_object: HazardReports|Users|Roles
    ) -> None:
        AuditLogs.objects.create(
            user_id=actor_id,
            action=action,
            module=module,
            description=description,
            payload=payload if payload else {},
            target_object=target_object
        )

    @staticmethod
    def log_create(
            *,
            actor: Users,
            module: AuditLogs.ModuleType,
            target_object: HazardReports|Users|Roles,
            target_identifier: int|str,
            payload: dict[str, Any]|None=None,
            description_override: str|None=None
    ) -> None:
        description = description_override

        if not description:
            description = f"{module.value} {target_identifier} was created by {actor.user_number}"

        AuditLogService._log(
            actor_id=actor.user_id,
            action=AuditLogs.ActionType.CREATE,
            module=module,
            description=description,
            payload=payload,
            target_object=target_object
        )

    @staticmethod
    def log_update(
            *,
            actor: Users,
            module: AuditLogs.ModuleType,
            target_object: Users|Roles,
            description: str,
            payload: dict[str, Any]|None=None,
    ) -> None:

        AuditLogService._log(
            actor_id=actor.user_id,
            action=AuditLogs.ActionType.UPDATE,
            module=module,
            description=description,
            payload=payload,
            target_object=target_object
        )

    @staticmethod
    def log_deactivate(
            *,
            actor: Users,
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
                f"{deactivated_user_number} ({deactivated_user_role_name}) was deactivated by {actor.user_number}"
            ) + f" with the reason: \"{reason}\""

        AuditLogService._log(
            actor_id=actor.user_id,
            action=AuditLogs.ActionType.DEACTIVATE,
            module=module,
            description=description,
            payload=payload,
            target_object=deactivated_user
        )

    @staticmethod
    def log_warning(
            *,
            user: Users,
            warned_user: Users,
            reason: str,
            warning_number: str,
            report_number: str|None=None,
    ) -> None:
        description = (
            f"{warned_user.user_number} was issued a warning by {user.user_number}"
            f" with the reason: \"{reason}\""
        )
        if report_number:
            description += f" (linked report: {report_number})"

        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.WARNING,
            module=AuditLogs.ModuleType.USER,
            description=description,
            payload={"warning_number": warning_number, "reason": reason, "report_number": report_number},
            target_object=warned_user
        )

    @staticmethod
    def log_ban(
            *,
            user: Users,
            banned_user: Users,
            reason: str,
            fast_track_report_number: str|None=None,
    ) -> None:
        description = (
            f"{banned_user.user_number} ({banned_user.role.role_name}) was banned by {user.user_number}"
            f" with the reason: \"{reason}\""
        )
        if fast_track_report_number:
            description += f" (fast-track evidence: {fast_track_report_number})"

        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.BAN,
            module=AuditLogs.ModuleType.USER,
            description=description,
            payload={"reason": reason, "fast_track_report_number": fast_track_report_number},
            target_object=banned_user
        )

    @staticmethod
    def log_unban(
            *,
            user: Users,
            unbanned_user: Users,
            reason: str,
    ) -> None:
        AuditLogService._log(
            user_id=user.user_id,
            action=AuditLogs.ActionType.UNBAN,
            module=AuditLogs.ModuleType.USER,
            description=(
                f"{unbanned_user.user_number} ({unbanned_user.role.role_name}) was unbanned by {user.user_number}"
                f" with the reason: \"{reason}\""
            ),
            payload={"reason": reason},
            target_object=unbanned_user
        )

    @staticmethod
    def log_report_status_change(
            *,
            actor: Users|None,
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
            actor_str = actor.user_number if actor else 'the System'
            description_remarks = f" with the remarks: \"{remarks}\"" if remarks else ""

            old_status = old_status.upper()
            new_status = new_status.upper()
            description = (
                f"REPORT {report.report_number} status was changed from {old_status} to {new_status} by {actor_str}"
            ) + description_remarks

        AuditLogService._log(
            actor_id=actor.user_id if actor else None,
            action=AuditLogs.ActionType.STATUS_CHANGE,
            module=AuditLogs.ModuleType.REPORT,
            description=description,
            payload=payload,
            target_object=report
        )

    @staticmethod
    def log_report_severity_change(
            *,
            actor: Users,
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
            actor = actor.user_number

            description = (
                f"REPORT {report.report_number} severity was changed from {old_severity} to {new_severity} by {actor}"
            )

        AuditLogService._log(
            actor_id=actor.user_id,
            action=AuditLogs.ActionType.SEVERITY_CHANGE,
            module=AuditLogs.ModuleType.REPORT,
            description=description,
            payload=payload,
            target_object=report
        )

    @staticmethod
    def _authorized_audit_logs(user: Users):
        allowed_modules = []
        if AuthorizationService.has_perm(user, AllPermissions.AUDITS.READ_SYSTEM_LOGS):
            allowed_modules.extend([
                module.value
                for module in AuditLogs.ModuleType.get_system_modules()
            ])

        if AuthorizationService.has_perm(user, AllPermissions.AUDITS.READ_REPORT_LOGS):
            allowed_modules.extend([
                module.value
                for module in AuditLogs.ModuleType.get_report_modules()
            ])

        queryset = AuditLogs.objects.filter(module__in=allowed_modules)

        return queryset

    @staticmethod
    def list_authorized_audit_logs(
            *,
            user: Users,
            query_filters: dict[str, Any]
    ) -> DomainResult[AuditLogs]:
        authorized_audit_logs = AuditLogService._authorized_audit_logs(user)

        queryset = authorized_audit_logs.select_related(
            "user",
            "user__role"
        )

        filter_map = {
            "module": "module",
            "from_date": "created_at__date__gte",
            "to_date": "created_at__date__lte",
        }

        filters = {
            filter_map[field]: value
            for field, value in query_filters.items()
            if field in filter_map and value is not None
        }

        if filters:
            queryset = queryset.filter(**filters)

        role_id: int|None = query_filters.get("role_id")
        if role_id is not None:
            if role_id == 0:
                queryset = queryset.filter(user__isnull=True)
            else:
                queryset = queryset.filter(user__role__role_id=role_id)

        search_query: str|None = query_filters.get("q")
        if search_query:
            search_query = search_query.strip()

            queryset = queryset.filter(
                Q(audit_log_number__icontains=search_query) |
                Q(user__user_number__icontains=search_query)
            )

        return DomainResult.success(queryset.order_by("-created_at"))

    @staticmethod
    def get_authorized_audit_log(
            *,
            user: Users,
            audit_log_number: str
    ) -> DomainResult[AuditLogs]:
        authorized_audit_logs = AuditLogService._authorized_audit_logs(user)

        audit_log = authorized_audit_logs.filter(
            audit_log_number__iexact=audit_log_number
        ).select_related(
            "user",
            "user__role"
        ).first()

        if not audit_log:
            raise AuditLogNotFoundException()

        return DomainResult.success(audit_log)
