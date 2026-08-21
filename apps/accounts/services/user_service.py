from apps.accounts.models.role_model import Roles
from apps.accounts.models.user_model import Users
from apps.accounts.exceptions.role_exception import SystemCitizenRoleMissingException, RoleNotFoundException
from shared.authorization.default_initial_role import AllDefaultRoles
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
            is_verified=True,
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