import string
import secrets
import hmac
import hashlib
from typing import Any
from datetime import date

from django.contrib.auth.hashers import make_password
from django.db.models import Case, When, Value, IntegerField, Q, Count
from django.db import transaction
from django.conf import settings

from apps.accounts.models.role_model import Roles
from apps.accounts.models.user_model import Users
from apps.audits.services import AuditLogService
from apps.accounts.exceptions.role_exception import SystemCitizenRoleMissingException, RoleNotFoundException
from apps.accounts.domain_errors.user_error import (
    UserNotFoundError,
    IncorrectAccountCredentialsError,
    SelfUpdateDeniedError
)
from shared.authorization.default_initial_role import AllDefaultRoles
from shared.authorization.service import AuthorizationService
from shared.authorization import AllPermissions
from shared.results import DomainResult
from apps.accounts.services import AuthService
from external.storage import StorageService, UploadIntent
from external.email import EmailService


class UserService:
    @staticmethod
    def _generate_secure_temp_password(length: int=12) -> str:
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        symbols = "!@#$%&*"
        all_chars = lowercase + uppercase + digits + symbols

        required_chars = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(symbols),
        ]
        required_chars += [secrets.choice(all_chars) for _ in range(length - 4)]

        secrets.SystemRandom().shuffle(required_chars)

        return ''.join(required_chars)

    @staticmethod
    def create_verified_citizen(
            *,
            email: str,
            password_hash: str,
            last_name: str,
            first_name: str,
            middle_name: str | None = None
    ) -> DomainResult[Users]:
        _protected_citizen_role = AllDefaultRoles.get_citizen_role()
        citizen_role: Roles = Roles.objects.get_by_code_or_none(_protected_citizen_role.code)

        if not citizen_role:
            raise SystemCitizenRoleMissingException()

        user: Users = Users.objects.create_user(
            email=email,
            password_hash=password_hash,
            role=citizen_role,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name if middle_name else None,
        )

        return DomainResult.success(user)


    @staticmethod
    @transaction.atomic
    def create_staff(
            *,
            actor: Users,
            email: str,
            role_id: int,
            last_name: str,
            first_name: str,
            middle_name: str | None = None,
            contact_number: str,
            birth_date: date,
            gender: str,
            street_address: str,
            region_code: str,
            province_code: str,
            city_code: str,
            barangay_code: str
    ) -> DomainResult[Users]:
        staff_role: Roles = Roles.objects.get_by_id_or_none(role_id)

        if not staff_role:
            raise RoleNotFoundException()

        temp_password = UserService._generate_secure_temp_password()

        user: Users = Users.objects.create_user(
            email=email,
            password=temp_password,
            role=staff_role,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name if middle_name else None,
            is_staff=True,
            must_change_password=True,
            contact_number=contact_number,
            birth_date=birth_date,
            gender=gender,
            street_address=street_address,
            region_code=region_code,
            province_code=province_code,
            city_code=city_code,
            barangay_code=barangay_code
        )

        AuditLogService.log_create(
            actor=actor,
            module=AuditLogService.ModuleType.EMPLOYEE,
            target_object=user,
            target_identifier=user.user_number,
            payload={
                "assigned_role": {
                    "role_id": staff_role.role_id,
                    "role_code": staff_role.role_code,
                    "role_name": staff_role.role_name,
                }
            }
        )

        # Only sent once the surrounding transaction commits: a rolled-back
        # staff creation must not leak the temporary password by email.
        transaction.on_commit(
            lambda: EmailService.send_employee_creation_temporary_password(
                to_email=user.email,
                to_first_name=user.first_name,
                user_number=user.user_number,
                assigned_role=staff_role.role_name,
                temp_password=temp_password,
            )
        )

        return DomainResult.success(user)

    @staticmethod
    def unauthenticated_change_password(
            *,
            email: str,
            new_password: str,
    ) -> DomainResult[Users]:
        user = Users.objects.get_by_active_email_or_none(email)

        if user is None:
            return DomainResult.error(UserNotFoundError)

        user.password = make_password(new_password)

        user.save(update_fields=["password", "updated_at"])

        return DomainResult.success(user)

    @staticmethod
    def get_next_staff_for_assignment(staff_to_active_report_map: dict[int, int]) -> Users|None:
        queryset = Users.objects.filter(
            is_staff=True,
            is_active=True,
            role__permissions__permission_name=AllPermissions.REPORTS.UPDATE_ASSIGNED.name,
        ).distinct()

        if not queryset.exists():
            return None

        when_clauses = [
            When(user_id=user_id, then=Value(count))
            for user_id, count in staff_to_active_report_map.items()
        ]

        queryset = queryset.annotate(
            active_report=Case(
                *when_clauses,
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        return queryset.order_by('active_report', 'created_at').first()

    @staticmethod
    def list_assignment_handlers(query_filters: dict[str, Any]|None=None) -> DomainResult[Users]:
        # Eligible transfer targets match the auto-assignment pool: active
        # staff whose role can update assigned reports.
        queryset = Users.objects.filter(
            is_staff=True,
            is_active=True,
            role__permissions__permission_name=AllPermissions.REPORTS.UPDATE_ASSIGNED.name,
        ).select_related(
            "role"
        ).distinct()

        search_query = (query_filters or {}).get("q")
        if search_query:
            search_tokens = search_query.strip().split()

            for token in search_tokens:
                queryset = queryset.filter(
                    Q(user_number__icontains=token) |
                    Q(email__icontains=token) |
                    Q(last_name__icontains=token) |
                    Q(first_name__icontains=token) |
                    Q(middle_name__icontains=token)
                )

        return DomainResult.success(queryset.order_by("last_name", "first_name"))

    @staticmethod
    @transaction.atomic
    def authenticated_change_password(
            *,
            user: Users,
            current_refresh_token: str,
            current_password: str,
            new_password: str,
    ) -> DomainResult[None]:
        if user.check_password(current_password):
            user.password = make_password(new_password)
            user.save(update_fields=["password", "updated_at"])

            AuthService.revoke_other_refresh_tokens(
                user=user,
                current_refresh_token=current_refresh_token
            )

            return DomainResult.success(None)

        return DomainResult.error(IncorrectAccountCredentialsError)

    @staticmethod
    @transaction.atomic
    def deactivate_account(user: Users) -> DomainResult[None]:
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])

            transaction.on_commit(
                lambda: EmailService.send_user_self_deactivation(
                    to_email=user.email,
                    to_first_name=user.first_name,
                    full_name=user.get_full_name(),
                )
            )

        return DomainResult.success(None)

    @staticmethod
    def update_profile(
            *,
            user: Users,
            fields: dict[str, Any],
    ) -> DomainResult[None]:
        if fields:
            updated_fields: list[str] = []

            for field, value in fields.items():
                setattr(user, field, value)
                updated_fields.append(field)

            if updated_fields:
                updated_fields.append("updated_at")
                user.save(update_fields=updated_fields)

        return DomainResult.success(None)

    @staticmethod
    def get_profile_image_upload_credentials(user: Users) -> DomainResult[dict[str, Any]]:
        key = settings.SECRET_KEY.encode('utf-8')
        user_attr = f"pfp:{user.user_id}".encode('utf-8')

        secure_hash = hmac.new(key, user_attr, hashlib.sha256).hexdigest()

        folder_path = f"{UploadIntent.USER_PROFILES.value}"
        file_name = f"{secure_hash}_pfp"

        upload_credential = StorageService.get_upload_credentials(
            folder_path=folder_path,
            file_names=[file_name],
            intent=UploadIntent.USER_PROFILES
        )

        return DomainResult.success(upload_credential)

    @staticmethod
    def list_users(
            *,
            is_staff: bool,
            query_filters: dict[str, Any]
    ) -> DomainResult[Users]:
        queryset = Users.objects.filter(
            is_staff=is_staff
        ).select_related(
            "role"
        )

        if not is_staff:
            queryset = queryset.annotate(
                warning_count=Count("received_warnings")
            )

        filter_map = {
            "is_active": "is_active",
            "role_id": "role_id",
        }

        filters = {
            filter_map[field]: value
            for field, value in query_filters.items()
            if field in filter_map and value is not None
        }

        if filters:
            queryset = queryset.filter(**filters)

        search_query = query_filters.get("q")
        if search_query:
            search_tokens = search_query.strip().split()

            for token in search_tokens:
                queryset = queryset.filter(
                    Q(user_number__icontains=token) |
                    Q(email__icontains=token) |
                    Q(last_name__icontains=token) |
                    Q(first_name__icontains=token) |
                    Q(middle_name__icontains=token)
                )

        return DomainResult.success(queryset.order_by("-created_at"))

    @staticmethod
    def get_user(
            *,
            user_number: str,
            is_staff: bool,
    ) -> DomainResult[Users]:
        queryset = Users.objects.filter(
            user_number__iexact=user_number,
            is_staff=is_staff
        ).select_related("role")

        if not is_staff:
            queryset = queryset.annotate(
                warning_count=Count("received_warnings")
            )

        user = queryset.first()

        if user is None:
            return DomainResult.error(UserNotFoundError)

        return DomainResult.success(user)

    @staticmethod
    @transaction.atomic
    def update_staff(
            *,
            actor: Users,
            user_number: str,
            fields: dict[str, Any],
    ) -> DomainResult[None]:
        if actor.user_number.lower() == user_number.lower():
            return DomainResult.error(SelfUpdateDeniedError)

        user = Users.objects.filter(
            user_number__iexact=user_number,
            is_staff=True
        ).first()

        if user is None:
            return DomainResult.error(UserNotFoundError)

        updated_fields: list[str] = []
        changes: dict[str, dict[str, Any]] = {}
        is_active: bool|None = fields.get("is_active")
        role_id: int|None = fields.get("role_id")

        info_fields: list[str] = [
            "email",
            "last_name",
            "first_name",
            "middle_name",
            "contact_number",
            "birth_date",
            "gender",
            "street_address",
            "region_code",
            "province_code",
            "city_code",
            "barangay_code",
        ]

        updated_info_fields: dict[str, Any] = {
            field: fields.get(field)
            for field in info_fields
            if field in fields and fields[field] != getattr(user, field)
        }

        if updated_info_fields:
            AuthorizationService.require_perm(actor, AllPermissions.EMPLOYEES.UPDATE_ANY)
            for field, value in updated_info_fields.items():
                changes[field] = {"from": getattr(user, field), "to": value}
                setattr(user, field, value)
                updated_fields.append(field)

        if is_active is not None and is_active != user.is_active:
            if is_active is True:
                AuthorizationService.require_perm(actor, AllPermissions.EMPLOYEES.ACTIVATE_ANY)
            else:
                AuthorizationService.require_perm(actor, AllPermissions.EMPLOYEES.DEACTIVATE_ANY)

            changes["is_active"] = {"from": user.is_active, "to": is_active}
            user.is_active = is_active
            updated_fields.append("is_active")

        if role_id is not None and role_id != user.role_id:
            AuthorizationService.require_perm(actor, AllPermissions.EMPLOYEES.ASSIGN_ROLE)

            role = Roles.objects.get_by_id_or_none(role_id)
            if role is None:
                raise RoleNotFoundException()

            changes["role"] = {
                "from": {"role_id": user.role_id, "role_name": user.role.role_name},
                "to": {"role_id": role.role_id, "role_name": role.role_name},
            }
            user.role = role
            updated_fields.append("role_id")

        if updated_fields:
            updated_fields.append("updated_at")
            user.save(update_fields=updated_fields)

            changed_fields = ", ".join(changes.keys())
            is_deactivation = changes.get("is_active", {}).get("to") is False

            if is_deactivation:
                AuditLogService.log_deactivate(
                    actor=actor,
                    module=AuditLogService.ModuleType.EMPLOYEE,
                    target_object=user,
                    payload_override={"changes": changes},
                    description_override=(
                        f"EMPLOYEE {user.user_number} was deactivated by {actor.user_number}"
                        f" (fields: {changed_fields})"
                    ),
                )
            else:
                AuditLogService.log_update(
                    actor=actor,
                    module=AuditLogService.ModuleType.EMPLOYEE,
                    target_object=user,
                    description=(
                        f"EMPLOYEE {user.user_number} was updated by {actor.user_number}"
                        f" (fields: {changed_fields})"
                    )[:255],
                    payload={"changes": changes},
                )

        return DomainResult.success(None)

    @staticmethod
    @transaction.atomic
    def update_citizen(
            *,
            actor: Users,
            user_number: str,
            fields: dict[str, Any],
    ) -> DomainResult[None]:
        user = Users.objects.filter(
            user_number__iexact=user_number,
            is_staff=False
        ).first()

        if user is None:
            return DomainResult.error(UserNotFoundError)

        updated_fields: list[str] = []
        changes: dict[str, dict[str, Any]] = {}
        is_active = fields.get("is_active")

        if is_active is not None and is_active != user.is_active:
            if is_active is True:
                AuthorizationService.require_perm(actor, AllPermissions.USERS.ACTIVATE_ANY)
            else:
                AuthorizationService.require_perm(actor, AllPermissions.USERS.DEACTIVATE_ANY)

            changes["is_active"] = {"from": user.is_active, "to": is_active}
            user.is_active = is_active
            updated_fields.append("is_active")

        if updated_fields:
            updated_fields.append("updated_at")
            user.save(update_fields=updated_fields)

            if changes["is_active"]["to"] is False:
                AuditLogService.log_deactivate(
                    actor=actor,
                    module=AuditLogService.ModuleType.USER,
                    target_object=user,
                    payload_override={"changes": changes},
                    description_override=(
                        f"{user.user_number} was deactivated by {actor.user_number}"
                    ),
                )
            else:
                AuditLogService.log_update(
                    actor=actor,
                    module=AuditLogService.ModuleType.USER,
                    target_object=user,
                    description=(
                        f"{user.user_number} was activated by {actor.user_number}"
                    ),
                    payload={"changes": changes},
                )

        return DomainResult.success(None)

