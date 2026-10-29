import re
from typing import Any, ClassVar
from collections import defaultdict

from django.db import transaction
from django.db.models import Q

from apps.accounts.models import Roles, Permissions
from shared.results import DomainResult
from shared.authorization.default_initial_role import AllDefaultRoles
from apps.audits.services import AuditLogService
from apps.accounts.models import Users
from apps.accounts.exceptions.role_exception import (
    RoleNotFoundException,
    SystemProtectedRoleModificationDeniedException,
    DeactivatedRoleModificationDeniedException
)
from apps.accounts.domain_errors.role_error import RoleAlreadyExistError, PermissionNotFoundError, RoleInUseError


class RoleService:
    @staticmethod
    def list_roles_for_lookup(*, exclude_citizen: bool = False) -> DomainResult[Roles]:
        roles = Roles.objects.filter(is_active=True)

        if exclude_citizen:
            roles = roles.exclude(
                role_code=AllDefaultRoles.get_citizen_role().code
            )

        return DomainResult.success(roles.values("role_id", "role_name"))

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
    def list_roles(query_filters: dict[str, Any]) -> DomainResult[Roles]:
        queryset = Roles.objects.all().prefetch_related("permissions")

        filter_map = {
            "is_active": "is_active",
        }

        filters = {
            filter_map[field]: value
            for field, value in query_filters.items()
            if field in filter_map and value is not None
        }

        if filters:
            queryset = queryset.filter(**filters)

        search_query: str|None = query_filters.get("q")
        if search_query:
            search_query = search_query.strip()

            queryset = queryset.filter(
                Q(role_name__icontains=search_query)
            )

        return DomainResult.success(queryset.order_by("-created_at"))

    @staticmethod
    def get_role(role_id: int) -> DomainResult[Roles]:
        queryset = Roles.objects.filter(role_id=role_id).prefetch_related("permissions").first()
        return DomainResult.success(queryset)

    @staticmethod
    @transaction.atomic
    def create_role(
            *,
            actor: Users,
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

        role: Roles = Roles.objects.create(
            role_name=cleaned_role_name,
            role_code=role_code,
            description=description,
        )
        role.permissions.set(valid_permissions)

        AuditLogService.log_create(
            actor=actor,
            module=AuditLogService.ModuleType.ROLE,
            target_object=role,
            target_identifier=f"{role.role_code}({role.role_id})",
            payload={
                "role_details": {
                    "role_id": role.role_id,
                    "role_code": role.role_code,
                    "role_name": role.role_name,
                    "description": role.description,
                },
                "initial_permissions": list(valid_permissions.values_list("permission_name", flat=True)),
            }
        )

        return DomainResult.success(role)

    _CHANGE_FIELD_LABELS: ClassVar[dict[str, str]] = {
        "role_name": "Name",
        "role_code": "Code",
        "description": "Description",
    }

    @staticmethod
    def _describe_changes(changes: dict[str, dict[str, Any]]) -> str:
        parts: list[str] = []
        for field, change in changes.items():
            if field == "permissions":
                added = len(change.get("added") or [])
                removed = len(change.get("removed") or [])
                parts.append(f"Permissions +{added}/-{removed}")
            else:
                label = RoleService._CHANGE_FIELD_LABELS.get(
                    field,
                    field.replace("_", " ").title(),
                )
                parts.append(label)
        return ", ".join(parts)

    @staticmethod
    @transaction.atomic
    def update_role(
            *,
            actor: Users,
            role_id: int,
            fields: dict[str, Any],
    ) -> DomainResult[None]:
        role = Roles.objects.get_by_id_or_none(role_id)
        if not role:
            raise RoleNotFoundException()

        if role.is_protected:
            raise SystemProtectedRoleModificationDeniedException()

        if not role.is_active:
            raise DeactivatedRoleModificationDeniedException()

        updated_fields = []
        changes: dict[str, dict[str, Any]] = {}

        role_name: str|None = fields.get("role_name")
        description: str|None = fields.get("description")
        permission_names: list[str]|None = fields.get("permission_names")

        if role_name is not None and role_name.strip():
            cleaned_role_name = role_name.strip().title()
            role_code = Roles.format_role_code(cleaned_role_name)

            if role.role_code != role_code:
                if Roles.objects.filter(role_code=role_code).exists():
                    return DomainResult.error(RoleAlreadyExistError)

                changes["role_name"] = {"from": role.role_name, "to": cleaned_role_name}
                changes["role_code"] = {"from": role.role_code, "to": role_code}
                role.role_name = cleaned_role_name
                role.role_code = role_code
                updated_fields.extend(["role_name", "role_code"])

        if description is not None and description.strip() != role.description:
            changes["description"] = {"from": role.description, "to": description.strip()}
            role.description = description.strip()
            updated_fields.append("description")

        if updated_fields:
            updated_fields.append("updated_at")
            role.save(update_fields=updated_fields)

        if permission_names is not None:
            valid_permissions = Permissions.objects.filter(permission_name__in=permission_names)

            if valid_permissions.count() != len(set(permission_names)):
                return DomainResult.error(PermissionNotFoundError)

            old_permission_names = set(role.permissions.values_list("permission_name", flat=True))
            new_permission_names = set(valid_permissions.values_list("permission_name", flat=True))

            permissions_added = sorted(new_permission_names - old_permission_names)
            permissions_removed = sorted(old_permission_names - new_permission_names)

            role.permissions.set(valid_permissions)

            if permissions_added or permissions_removed:
                changes["permissions"] = {
                    "added": permissions_added,
                    "removed": permissions_removed,
                }

            if not updated_fields:
                role.save(update_fields=["updated_at"])

        if changes:
            changed_summary = RoleService._describe_changes(changes)
            AuditLogService.log_update(
                actor=actor,
                module=AuditLogService.ModuleType.ROLE,
                target_object=role,
                description=(
                    f"ROLE {role.role_code} was updated by {actor.user_number}"
                    f" (changed: {changed_summary})"
                ),
                payload={"changes": changes},
            )

        return DomainResult.success(None)

    @staticmethod
    @transaction.atomic
    def duplicate_role(
            *,
            actor: Users,
            role_id: int,
    ) -> DomainResult[Roles]:
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

        AuditLogService.log_create(
            actor=actor,
            module=AuditLogService.ModuleType.ROLE,
            target_object=new_role,
            target_identifier=f"{new_role.role_code}({new_role.role_id})",
            payload={
                "duplicated_from": {
                    "role_id": source_role.role_id,
                    "role_code": source_role.role_code,
                    "role_name": source_role.role_name,
                },
                "initial_permissions": list(source_permissions.values_list("permission_name", flat=True)),
            },
        )

        return DomainResult.success(new_role)

    @staticmethod
    @transaction.atomic
    def deactivate_role(
            *,
            actor: Users,
            role_id: int,
    ) -> DomainResult[None]:
        role = Roles.objects.get_by_id_or_none(role_id)

        if not role:
            raise RoleNotFoundException()

        if role.is_protected:
            raise SystemProtectedRoleModificationDeniedException()

        if not role.is_active:
            return DomainResult.success(None)

        if role.users.exists():
            return DomainResult.error(RoleInUseError)

        role.is_active = False
        role.save(update_fields=["is_active", "updated_at"])

        AuditLogService.log_deactivate(
            actor=actor,
            module=AuditLogService.ModuleType.ROLE,
            target_object=role,
            description_override=(
                f"ROLE {role.role_code} was deactivated by {actor.user_number}"
            ),
            payload_override={"changes": {"is_active": {"from": True, "to": False}}},
        )

        return DomainResult.success(None)
