from apps.accounts.models import Roles, Permissions
from shared.results import DomainResult


class RoleService:
    @staticmethod
    def list_roles() -> DomainResult[Roles]:
        queryset = Roles.objects.all()
        return DomainResult.success(queryset)

    @staticmethod
    def get_role(

    ):
        pass

    @staticmethod
    def list_permissions():
        pass
