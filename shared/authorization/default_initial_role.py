from dataclasses import dataclass, fields

from .definitions import RoleDefinition
from .all_permissions_registry import AllPermissions


@dataclass(frozen=True)
class AllDefaultRoleNames:
    SYSTEM_ADMIN = "System Admin"
    SUPERVISOR = "Supervisor"
    REPORT_OFFICER = "Report Officer"
    CITIZEN = "Citizen"


@dataclass(frozen=True)
class AllDefaultRoles:
    SYSTEM_ADMIN: RoleDefinition = RoleDefinition(
        name=AllDefaultRoleNames.SYSTEM_ADMIN,
        code=AllDefaultRoleNames.SYSTEM_ADMIN.upper(),
        description=" ".join("""Grants the permission to view, manage, and deactivate user and employee accounts, 
        role-based access control (RBAC) configurations, and view audit logs.""".split()),
        is_protected=False,
        permissions=(
            AllPermissions.USERS.READ_ALL,
            AllPermissions.USERS.DEACTIVATE_ANY,
            AllPermissions.USERS.ACTIVATE_ANY,

            AllPermissions.EMPLOYEES.CREATE,
            AllPermissions.EMPLOYEES.READ_ALL,
            AllPermissions.EMPLOYEES.ASSIGN_ROLE,
            AllPermissions.EMPLOYEES.DEACTIVATE_ANY,
            AllPermissions.EMPLOYEES.ACTIVATE_ANY,

            AllPermissions.ROLES.CREATE,
            AllPermissions.ROLES.READ_ALL,
            AllPermissions.ROLES.UPDATE_ANY,

            AllPermissions.ANALYTICS.READ_EMPLOYEE_METRICS,

            AllPermissions.AUDITS.READ_REPORT_LOGS,
            AllPermissions.AUDITS.READ_SYSTEM_LOGS,
        ),
        mandatory_permissions=(
            AllPermissions.ROLES.READ_ALL.name,
            AllPermissions.ROLES.UPDATE_ANY.name,
        )
    )

    SUPERVISOR: RoleDefinition = RoleDefinition(
        name=AllDefaultRoleNames.SUPERVISOR,
        code=AllDefaultRoleNames.SUPERVISOR.upper(),
        description=" ".join("""Grants the permission to view the timeline of reports, 
        system-wide analytics and metric, and audit logs.""".split()),
        is_protected=False,
        permissions=(
            AllPermissions.REPORTS.READ_ALL,

            AllPermissions.ANALYTICS.READ_EMPLOYEE_METRICS,
            AllPermissions.ANALYTICS.READ_ALL_METRICS,
            AllPermissions.ANALYTICS.READ_DASHBOARD,

            AllPermissions.AUDITS.READ_REPORT_LOGS,
        )
    )

    REPORT_OFFICER: RoleDefinition = RoleDefinition(
        name=AllDefaultRoleNames.REPORT_OFFICER,
        code=AllDefaultRoleNames.REPORT_OFFICER.upper(),
        description=" ".join("""Grants the permission to view, manage and process assigned reports.""".split()),
        is_protected=False,
        permissions=(
            AllPermissions.REPORTS.READ_ASSIGNED,
            AllPermissions.REPORTS.UPDATE_ASSIGNED,

            AllPermissions.ANALYTICS.READ_ASSIGNED_METRICS,
        )
    )

    CITIZEN: RoleDefinition = RoleDefinition(
        name=AllDefaultRoleNames.CITIZEN,
        code=AllDefaultRoleNames.CITIZEN.upper(),
        description=" ".join("""Grants the permission to view, create, and update their own reports and 
        read, manage, and deactivate their own user account.""".split()),
        is_protected=True,
        permissions=(
            AllPermissions.REPORTS.CREATE,
            AllPermissions.REPORTS.READ_OWN,
            AllPermissions.REPORTS.UPDATE_OWN,

            AllPermissions.USERS.READ_OWN,
            AllPermissions.USERS.UPDATE_OWN,
            AllPermissions.USERS.DEACTIVATE_OWN,

            AllPermissions.ANALYTICS.READ_OWN_METRICS,
        )
    )


    @classmethod
    def get_citizen_role(cls) -> RoleDefinition:
        return cls.CITIZEN

    @classmethod
    def get_flat_list(cls) -> list[RoleDefinition]:
        all_roles = []

        for role in fields(cls):
            all_roles.append(role.default)

        return all_roles

    @classmethod
    def get_protected_roles(cls) -> list[RoleDefinition]:
        all_protected_roles = []

        for role in cls.get_flat_list():
            if role.is_protected:
                all_protected_roles.append(role)

        return all_protected_roles