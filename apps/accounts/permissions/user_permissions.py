from dataclasses import dataclass

from shared.authorization.definitions import PermissionDefinition


_module: str = 'users'

@dataclass(frozen=True)
class UserPermissions:
    READ_OWN: PermissionDefinition = PermissionDefinition(
        name='user:read_own',
        description='Allows the role to READ their own user information',
        module=_module
    )

    UPDATE_OWN: PermissionDefinition = PermissionDefinition(
        name='user:update_own',
        description='Allows the role to UPDATE their own user information',
        module=_module
    )

    DEACTIVATE_OWN: PermissionDefinition = PermissionDefinition(
        name='user:deactivate_own',
        description='Allows the role to DEACTIVATE their own account',
        module=_module
    )

    READ_ALL: PermissionDefinition = PermissionDefinition(
        name='user:read_all',
        description='Allows the role to READ all user accounts',
        module=_module
    )

    DEACTIVATE_ANY: PermissionDefinition = PermissionDefinition(
        name='user:deactivate_any',
        description='Allows the role to DEACTIVATE any user accounts',
        module=_module
    )

    ACTIVATE_ANY: PermissionDefinition = PermissionDefinition(
        name='user:activate_any',
        description='Allows the role to ACTIVATE any user accounts',
        module=_module
    )
