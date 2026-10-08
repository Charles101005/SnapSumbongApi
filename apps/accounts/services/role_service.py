from typing import Any
from collections import defaultdict

from apps.accounts.models import Roles, Permissions
from shared.results import DomainResult


class RoleService:
    @staticmethod
    def list_roles_for_lookup() -> DomainResult[Roles]:
        roles = Roles.objects.values("role_id", "role_name")
        return DomainResult.success(roles)

    @staticmethod
    def list_permissions_grouped_by_module() -> DomainResult[dict[str, list[dict[str, Any]]]]:
        all_permissions = Permissions.objects.all().order_by("module", "permission_name")

        grouped_permissions = defaultdict(list)
        for permission in all_permissions:
            module = permission.module.upper()

            grouped_permissions[module].append({
                "permission_name": permission.permission_name,
                "description": permission.description,
            })

        return DomainResult.success(grouped_permissions)

    @staticmethod
    def list_roles() -> DomainResult[Roles]:
        queryset = Roles.objects.all().prefetch_related("permissions")
        return DomainResult.success(queryset.order_by("role_id"))

    @staticmethod
    def get_role(role_id: int) -> DomainResult[Roles]:
        queryset = Roles.objects.filter(role_id=role_id).prefetch_related("permissions").first()
        return DomainResult.success(queryset)

    @staticmethod
    def create_role(
            *,
            role_name: str,
            description: str,
            permissions: list[str]
    ) -> DomainResult[None]:
        pass
