from rest_framework.exceptions import PermissionDenied

from apps.accounts.models.user_model import Users
from .definitions import PermissionDefinition

class AuthorizationService:
    _PERMS_CACHE_ATTR = "_permission_cache"

    @classmethod
    def get_perms(cls, user: Users) -> set[str]:
        cached_perms = getattr(user, cls._PERMS_CACHE_ATTR, None)

        if cached_perms is not None:
            return cached_perms

        permissions = set(
            user.role.permissions.values_list("permission_name", flat=True)
        )

        setattr(user, cls._PERMS_CACHE_ATTR, permissions)

        return permissions

    @classmethod
    def has_perm(cls, user: Users, permission: PermissionDefinition) -> bool:
        return permission.name in cls.get_perms(user)

    @classmethod
    def require_perm(cls, user: Users, permission: PermissionDefinition) -> None:
        if not cls.has_perm(user, permission):
            raise PermissionDenied()


    @classmethod
    def require_all_perms(cls, user: Users, permissions: tuple[PermissionDefinition, ...]) -> None:
        user_perms = cls.get_perms(user)

        required_perms = set(
            permission.name
            for permission in permissions
        )

        if required_perms.difference(user_perms):
            raise PermissionDenied()

    @classmethod
    def require_any_perms(cls, user: Users, permissions: tuple[PermissionDefinition, ...]) -> None:
        user_perms = cls.get_perms(user)

        required_perms = set(
            permission.name
            for permission in permissions
        )

        if not required_perms.intersection(user_perms):
            raise PermissionDenied()