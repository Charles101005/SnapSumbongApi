from dataclasses import dataclass

from shared.authorization.definitions import PermissionDefinition


_module = 'employees'

@dataclass(frozen=True)
class EmployeePermissions:
    CREATE: PermissionDefinition = PermissionDefinition(
        name='employee:create',
        description='Allows the role to CREATE employees',
        module=_module,
    )

    READ_ALL: PermissionDefinition = PermissionDefinition(
        name='employee:read_all',
        description='Allows the role to READ all employees',
        module=_module,
    )

    ASSIGN_ROLE: PermissionDefinition = PermissionDefinition(
        name='employee:assign_role',
        description='Allows the role to ASSIGN roles to employees',
        module=_module,
    )

    DEACTIVATE_ANY: PermissionDefinition = PermissionDefinition(
        name='employee:deactivate_any',
        description='Allows the role to DEACTIVATE any employee',
        module=_module,
    )

    ACTIVATE_ANY: PermissionDefinition = PermissionDefinition(
        name='employee:activate_any',
        description='Allows the role to ACTIVATE any employee',
        module=_module,
    )