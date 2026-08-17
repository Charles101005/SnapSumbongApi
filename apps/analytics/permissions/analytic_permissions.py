from dataclasses import dataclass

from shared.authorization.definitions import PermissionDefinition


_module = 'analytics'

@dataclass(frozen=True)
class AnalyticPermissions:
    READ_OWN_METRICS: PermissionDefinition = PermissionDefinition(
        name='analytic:read_own_metrics',
        description='Allows the role to READ their own hazard report metrics',
        module=_module,
    )

    READ_ASSIGNED_METRICS: PermissionDefinition = PermissionDefinition(
        name='analytic:read_assigned_metrics',
        description='Allows the role to READ metrics for hazard reports assigned to them',
        module=_module,
    )

    READ_EMPLOYEE_METRICS: PermissionDefinition = PermissionDefinition(
        name='analytic:read_employee_metrics',
        description='Allows the role to READ performance metrics of employees',
        module=_module,
    )

    READ_ALL_METRICS: PermissionDefinition = PermissionDefinition(
        name='analytic:read_all_metrics',
        description='Allows the role to READ system-wide metrics',
        module=_module,
    )

    READ_DASHBOARD: PermissionDefinition = PermissionDefinition(
        name='analytic:read_dashboard',
        description='Allows the role to READ the analytics dashboard',
        module=_module,
    )