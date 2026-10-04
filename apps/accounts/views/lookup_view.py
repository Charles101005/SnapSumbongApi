from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import api_view

from shared.results import DomainResultResponse
from apps.accounts.services import RoleService
from shared.authorization import AllPermissions
from shared.authorization.decorators import require_any_perms
from apps.accounts.serializers.response.lookup_serializer import LookupRolesResponseSerializer


@api_view(["GET"])
@require_any_perms(
    AllPermissions.EMPLOYEES.CREATE,
    AllPermissions.EMPLOYEES.READ_ALL,
    AllPermissions.EMPLOYEES.ASSIGN_ROLE,
)
def lookup_roles_view(request: Request) -> Response:
    result = RoleService.list_roles()

    return DomainResultResponse(result).respond(
        serializer_class=LookupRolesResponseSerializer,
        success_status_code=status.HTTP_200_OK,
        serializer_is_many=True,
    )
