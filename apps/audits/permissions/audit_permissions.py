from dataclasses import dataclass

from shared.authorization.definitions import PermissionDefinition


_module = 'audits'

@dataclass(frozen=True)
class AuditPermissions:
    READ_REPORT_LOGS: PermissionDefinition = PermissionDefinition(
        name='audit:read_report_logs',
        description='Allows the role to READ audit logs for hazard reports',
        module=_module,
    )

    READ_SYSTEM_LOGS: PermissionDefinition = PermissionDefinition(
        name='audit:read_system_logs',
        description='Allows the role to READ system audit logs',
        module=_module,
    )