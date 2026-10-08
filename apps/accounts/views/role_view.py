from rest_framework import status
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response

from shared.results import DomainResultResponse
from shared.authorization import AllPermissions
from shared.authorization.decorators import require_perm
from shared.pagination import SmallListPagination
from apps.accounts.services import RoleService
from apps.accounts.serializers.response.role_serializer import (
    ListRolesResponseSerializer,
    DetailRoleResponseSerializer
)


class RoleListView(APIView):
    require_perm(AllPermissions.ROLES.READ_ALL)
    def get(self, request: Request) -> Response:
        result = RoleService.list_roles()

        return DomainResultResponse(result).respond_with_pagination(
            request=request,
            pagination_class=SmallListPagination,
            serializer_class=ListRolesResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )

    require_perm(AllPermissions.ROLES.CREATE)
    def post(self, request: Request) -> Response:
        pass


class RoleDetailView(APIView):
    require_perm(AllPermissions.ROLES.READ_ALL)
    def get(self, request: Request, role_id: int) -> Response:
        result = RoleService.get_role(role_id)

        return DomainResultResponse(result).respond(
            serializer_class=DetailRoleResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )

    require_perm(AllPermissions.ROLES.UPDATE_ANY)
    def put(self, request: Request, role_id: int) -> Response:
        pass
