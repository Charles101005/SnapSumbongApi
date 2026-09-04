from django.contrib.auth.hashers import make_password
from django.db.models import Case, When, Value, IntegerField

from apps.accounts.models.role_model import Roles
from apps.accounts.models.user_model import Users
from apps.accounts.exceptions.role_exception import SystemCitizenRoleMissingException, RoleNotFoundException
from apps.accounts.domain_errors.user_error import UserNotFoundError
from shared.authorization.default_initial_role import AllDefaultRoles
from shared.authorization import AllPermissions
from shared.results import DomainResult


class UserService:
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
            middle_name=middle_name,
            has_changed_password=True,
        )

        return DomainResult.success(user)


    @staticmethod
    def create_staff(
            *,
            email: str,
            password: str,
            role_id: int,
            last_name: str,
            first_name: str,
            middle_name: str | None = None
    ) -> DomainResult[Users]:
        staff_role: Roles = Roles.objects.get_by_id_or_none(role_id)

        if not staff_role:
            raise RoleNotFoundException()

        user: Users = Users.objects.create_user(
            email=email,
            password=password,
            role=staff_role,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            is_staff=True,
        )

        return DomainResult.success(user)

    @staticmethod
    def change_password(
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
