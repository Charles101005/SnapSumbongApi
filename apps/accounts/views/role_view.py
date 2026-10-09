from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from shared.results import DomainResultResponse
from shared.authorization import AllPermissions
from shared.authorization.decorators import require_perm
from shared.pagination import SmallListPagination
from apps.accounts.services import RoleService
from apps.accounts.serializers.request.role_serializer import CreateUpdateRoleRequestSerializer
from apps.accounts.serializers.response.role_serializer import (
    ListRolesResponseSerializer,
    DetailRoleResponseSerializer,
    CreateRoleResponseSerializer
)


class RoleListView(APIView):
    @require_perm(AllPermissions.ROLES.READ_ALL)
    def get(self, request: Request) -> Response:
        result = RoleService.list_roles()

        return DomainResultResponse(result).respond_with_pagination(
            request=request,
            pagination_class=SmallListPagination,
            serializer_class=ListRolesResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )

    @require_perm(AllPermissions.ROLES.CREATE)
    def post(self, request: Request) -> Response:
        serializer = CreateUpdateRoleRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = RoleService.create_role(
            role_name=validated_data['role_name'],
            description=validated_data['description'],
            permission_names=validated_data['permission_names'],
        )

        return DomainResultResponse(result).respond(
            serializer_class=CreateRoleResponseSerializer,
            success_status_code=status.HTTP_201_CREATED,
        )


class RoleDetailView(APIView):
    @require_perm(AllPermissions.ROLES.READ_ALL)
    def get(self, request: Request, role_id: int) -> Response:
        result = RoleService.get_role(role_id)

        return DomainResultResponse(result).respond(
            serializer_class=DetailRoleResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )

    @require_perm(AllPermissions.ROLES.UPDATE_ANY)
    def patch(self, request: Request, role_id: int) -> Response:
        serializer = CreateUpdateRoleRequestSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = RoleService.update_role(
            role_id=role_id,
            fields=validated_data
        )

        return DomainResultResponse(result).respond(
            success_status_code=status.HTTP_200_OK,
        )


@api_view(["POST"])
@require_perm(AllPermissions.ROLES.CREATE)
def duplicate_role_view(request: Request, role_id: int) -> Response:
    result = RoleService.duplicate_role(role_id)

    return DomainResultResponse(result).respond(
        serializer_class=CreateRoleResponseSerializer,
        success_status_code=status.HTTP_201_CREATED,
    )
