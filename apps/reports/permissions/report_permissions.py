from dataclasses import dataclass

from shared.authorization.definitions import PermissionDefinition


_module = 'reports'

@dataclass(frozen=True)
class ReportPermissions:
    CREATE: PermissionDefinition = PermissionDefinition(
        name='report:create',
        description='Allows the role to CREATE hazard reports',
        module=_module,
    )

    READ_OWN: PermissionDefinition = PermissionDefinition(
        name='report:read_own',
        description='Allows the role to READ their own hazard reports',
        module=_module,
    )

    UPDATE_OWN: PermissionDefinition = PermissionDefinition(
        name='report:update_own',
        description='Allows the role to UPDATE their own hazard reports',
        module=_module,
    )

    READ_ASSIGNED: PermissionDefinition = PermissionDefinition(
        name='report:read_assigned',
        description='Allows the role to READ hazard reports assigned to them',
        module=_module,
    )

    UPDATE_ASSIGNED: PermissionDefinition = PermissionDefinition(
        name='report:update_assigned',
        description='Allows the role to UPDATE hazard reports assigned to them',
        module=_module,
    )

    READ_ALL: PermissionDefinition = PermissionDefinition(
        name='report:read_all',
        description='Allows the role to READ all hazard reports',
        module=_module,
    )