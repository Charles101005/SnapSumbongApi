import string
import secrets
import hmac
import hashlib
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db.models import Case, When, Value, IntegerField, Q
from django.db import transaction
from django.conf import settings

from apps.accounts.models.role_model import Roles
from apps.accounts.models.user_model import Users
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
            has_changed_password=True,
        )

        return DomainResult.success(user)


    @staticmethod
    def create_staff(
            *,
            email: str,
            role_code: str,
            last_name: str,
            first_name: str,
            middle_name: str | None = None
    ) -> DomainResult[Users]:
        staff_role: Roles = Roles.objects.get_by_code_or_none(role_code.upper())

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
        )

        #TODO: SnapSumbong - Email the password in a transaction on-commit
        print("Password:", temp_password)

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

        user.save(update_fields=['password'])

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
            user.save(update_fields=['password'])

            AuthService.revoke_other_refresh_tokens(
                user=user,
                current_refresh_token=current_refresh_token
            )

            return DomainResult.success(None)

        return DomainResult.error(IncorrectAccountCredentialsError)

    @staticmethod
    def deactivate_account(user: Users) -> DomainResult[None]:
        if user.is_active:
            user.is_active = False
            user.save(update_fields=['is_active'])

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
            is_staff=is_staff,
        ).select_related(
            "role"
        )

        filter_map = {
            "is_active": "is_active",
            "role_code": "role__role_code__iexact",
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

        return DomainResult.success(queryset.order_by("-last_active"))

    @staticmethod
    def get_user(
            *,
            user_number: str,
            is_staff: bool,
    ) -> DomainResult[Users]:
        user = Users.objects.filter(
            user_number__iexact=user_number,
            is_staff=is_staff
        ).select_related("role").first()

        if user is None:
            return DomainResult.error(UserNotFoundError)

        return DomainResult.success(user)

    @staticmethod
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
        ).select_related(
            "role"
        ).first()

        if user is None:
            return DomainResult.error(UserNotFoundError)

        updated_fields: list[str] = []
        is_active: bool|None = fields.get("is_active")
        role_code: str|None = fields.get("role_code")

        if is_active is not None and is_active != user.is_active:
            if is_active is True:
                AuthorizationService.require_perm(actor, AllPermissions.EMPLOYEES.ACTIVATE_ANY)
            else:
                AuthorizationService.require_perm(actor, AllPermissions.EMPLOYEES.DEACTIVATE_ANY)

            user.is_active = is_active
            updated_fields.append("is_active")

        if role_code is not None and role_code.upper() != user.role.role_code:
            AuthorizationService.require_perm(actor, AllPermissions.EMPLOYEES.ASSIGN_ROLE)

            role = Roles.objects.get_by_code_or_none(role_code.upper())
            if role is None:
                raise RoleNotFoundException()

            user.role = role
            updated_fields.append("role_id")

        if updated_fields:
            user.save(update_fields=updated_fields)

        return DomainResult.success(None)

    @staticmethod
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
        is_active = fields.get("is_active")

        if is_active is not None and is_active != user.is_active:
            if is_active is True:
                AuthorizationService.require_perm(actor, AllPermissions.USERS.ACTIVATE_ANY)
            else:
                AuthorizationService.require_perm(actor, AllPermissions.USERS.DEACTIVATE_ANY)

            user.is_active = is_active
            updated_fields.append("is_active")

        if updated_fields:
            user.save(update_fields=updated_fields)

        return DomainResult.success(None)

