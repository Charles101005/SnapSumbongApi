import re
from typing import Any
from collections import defaultdict

from django.db import transaction

from apps.accounts.models import Roles, Permissions
from shared.results import DomainResult
from apps.accounts.exceptions.role_exception import (
    RoleNotFoundException,
    SystemProtectedRoleModificationDeniedException
)
from apps.accounts.domain_errors.role_error import RoleAlreadyExistError, PermissionNotFoundError


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
    @transaction.atomic
    def create_role(
            *,
            role_name: str,
            description: str,
            permission_names: list[str]
    ) -> DomainResult[Roles]:
        cleaned_role_name = role_name.strip().title()
        role_code = Roles.format_role_code(cleaned_role_name)
        if Roles.objects.filter(role_code=role_code).exists():
            return DomainResult.error(RoleAlreadyExistError)

        valid_permissions = Permissions.objects.filter(permission_name__in=permission_names)
        if valid_permissions.count() != len(set(permission_names)):
            return DomainResult.error(PermissionNotFoundError)

        role = Roles.objects.create(
            role_name=cleaned_role_name,
            role_code=role_code,
            description=description,
        )
        role.permissions.set(valid_permissions)

        return DomainResult.success(role)

    @staticmethod
    @transaction.atomic
    def update_role(
            *,
            role_id: int,
            fields: dict[str, Any],
    ) -> DomainResult[None]:
        role = Roles.objects.get_by_id_or_none(role_id)
        if not role:
            raise RoleNotFoundException()

        if role.is_protected:
            raise SystemProtectedRoleModificationDeniedException()

        updated_fields = []

        role_name: str|None = fields.get("role_name")
        description: str|None = fields.get("description")
        permission_names: list[str]|None = fields.get("permission_names")

        if role_name is not None and role_name.strip():
            cleaned_role_name = role_name.strip().title()
            role_code = Roles.format_role_code(cleaned_role_name)

            if role.role_code != role_code:
                if Roles.objects.filter(role_code=role_code).exists():
                    return DomainResult.error(RoleAlreadyExistError)

                role.role_name = cleaned_role_name
                role.role_code = role_code
                updated_fields.extend(["role_name", "role_code"])

        if description is not None and description.strip() != role.description:
            role.description = description.strip()
            updated_fields.append("description")

        if updated_fields:
            role.save(update_fields=updated_fields)

        if permission_names is not None:
            valid_permissions = Permissions.objects.filter(permission_name__in=permission_names)

            if valid_permissions.count() != len(set(permission_names)):
                return DomainResult.error(PermissionNotFoundError)

            role.permissions.set(valid_permissions)

        return DomainResult.success(None)

    @staticmethod
    @transaction.atomic
    def duplicate_role(role_id: int) -> DomainResult[Roles]:
        source_role: Roles|None = Roles.objects.filter(
            role_id=role_id
        ).prefetch_related("permissions").first()
        if not source_role:
            raise RoleNotFoundException()

        base_role_name = re.sub(r"_\d+$", "", source_role.role_name).strip()

        counter = 1
        while True:
            candidate_role_name = f"{base_role_name}_{counter}"
            candidate_role_code = Roles.format_role_code(candidate_role_name)

            if not Roles.objects.filter(role_code=candidate_role_code).exists():
                unique_role_name = candidate_role_name
                unique_role_code = candidate_role_code
                break

            counter += 1

        new_role = Roles.objects.create(
            role_name=unique_role_name,
            role_code=unique_role_code,
            description=f"Duplicate copy of {source_role.role_name} role.",
        )

        source_permissions = source_role.permissions.all()
        new_role.permissions.set(source_permissions)

        return DomainResult.success(new_role)
