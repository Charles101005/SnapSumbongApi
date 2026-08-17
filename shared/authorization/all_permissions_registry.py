from dataclasses import dataclass, fields

from .definitions import PermissionDefinition
from apps.accounts.permissions import UserPermissions, EmployeePermissions, RolePermissions
from apps.reports.permissions import ReportPermissions
from apps.analytics.permissions import AnalyticPermissions
from apps.audits.permissions import AuditPermissions


@dataclass(frozen=True)
class AllPermissions:
    USERS: UserPermissions = UserPermissions()
    EMPLOYEES: EmployeePermissions = EmployeePermissions()
    ROLES: RolePermissions = RolePermissions()
    REPORTS: ReportPermissions = ReportPermissions()
    ANALYTICS: AnalyticPermissions = AnalyticPermissions()
    AUDITS: AuditPermissions = AuditPermissions()


    @classmethod
    def get_flat_list(cls) -> list[PermissionDefinition]:
        all_permissions = []

        for domain_perms in fields(cls):
            for perms in fields(domain_perms.default):
                all_permissions.append(perms.default)

        return all_permissions