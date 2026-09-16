from functools import wraps

from .definitions import PermissionDefinition
from .service import AuthorizationService


def _get_request_from_args(args):
    if args and hasattr(args[0], 'user'):
        return args[0]

    if len(args) > 1 and hasattr(args[1], 'user'):
        return args[1]

    raise ValueError("Missing required 'request' argument")

def require_perm(permission: PermissionDefinition):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request = _get_request_from_args(args)
            AuthorizationService.require_perm(user=request.user, permission=permission)

            return func(*args, **kwargs)

        return wrapper
    return decorator

def require_all_perms(*permissions: PermissionDefinition):
    if not permissions:
        raise ValueError("Must have at least one permission")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request = _get_request_from_args(args)
            AuthorizationService.require_all_perms(user=request.user, permissions=permissions)

            return func(*args, **kwargs)

        return wrapper
    return decorator

def require_any_perms(*permissions: PermissionDefinition):
    if not permissions:
        raise ValueError("Must have at least one permission")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request = _get_request_from_args(args)
            AuthorizationService.require_any_perms(user=request.user, permissions=permissions)

            return func(*args, **kwargs)

        return wrapper
    return decorator