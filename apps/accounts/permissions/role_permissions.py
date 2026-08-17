from dataclasses import dataclass

from shared.authorization.definitions import PermissionDefinition


_module = 'roles'

@dataclass(frozen=True)
class RolePermissions:
    CREATE: PermissionDefinition = PermissionDefinition(
        name='role:create',
        description='Allows the role to CREATE roles',
        module=_module,
    )

    READ_ALL: PermissionDefinition = PermissionDefinition(
        name='role:read_all',
        description='Allows the role to READ all roles',
        module=_module,
    )

    UPDATE_ANY: PermissionDefinition = PermissionDefinition(
        name='role:update_any',
        description='Allows the role to UPDATE any role',
        module=_module,
    )