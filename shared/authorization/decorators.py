from functools import wraps

from .definitions import PermissionDefinition
from .service import AuthorizationService


def require_perm(permission: PermissionDefinition):
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            AuthorizationService.require_perm(user=request.user, permission=permission)

            return func(self, request, *args, **kwargs)

        return wrapper
    return decorator

def require_all_perms(*permissions: PermissionDefinition):
    if not permissions:
        raise ValueError("Must have at least one permission")

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            AuthorizationService.require_all_perms(user=request.user, permissions=permissions)

            return func(self, request, *args, **kwargs)

        return wrapper
    return decorator

def require_any_perms(*permissions: PermissionDefinition):
    if not permissions:
        raise ValueError("Must have at least one permission")

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            AuthorizationService.require_any_perms(user=request.user, permissions=permissions)

            return func(self, request, *args, **kwargs)

        return wrapper
    return decorator