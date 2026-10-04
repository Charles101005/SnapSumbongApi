from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView

from shared.results import DomainResultResponse
from shared.authorization import AllPermissions
from shared.authorization.decorators import require_perm, require_any_perms
from shared.pagination import SmallListPagination
from apps.accounts.services import UserService
from apps.accounts.serializers.request.user_serializer import UserUpdateRequestSerializer, UserListRequestSerializer
from apps.accounts.serializers.response.user_serializer import (
    UserListResponseSerializer,
    UserDetailResponseSerializer
)


class CitizenListView(APIView):
    @require_perm(AllPermissions.USERS.READ_ALL)
    def get(self, request: Request) -> Response:
        serializer = UserListRequestSerializer(
            data=request.query_params,
            context={"is_staff": False}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result =  UserService.list_users(
            is_staff=False,
            query_filters=validated_data
        )

        return DomainResultResponse(result).respond_with_pagination(
            request=request,
            pagination_class=SmallListPagination,
            serializer_class=UserListResponseSerializer,
            serializer_context={"is_staff": False},
            success_status_code=status.HTTP_200_OK,
        )


class CitizenDetailView(APIView):
    @require_perm(AllPermissions.USERS.READ_ALL)
    def get(self, request: Request, user_number: str) -> Response:
        result = UserService.get_user(
            user_number=user_number,
            is_staff=False,
        )

        return DomainResultResponse(result).respond(
            serializer_class=UserDetailResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )

    @require_any_perms(
        AllPermissions.USERS.ACTIVATE_ANY,
        AllPermissions.USERS.DEACTIVATE_ANY,
    )
    def patch(self, request: Request, user_number: str) -> Response:
        serializer = UserUpdateRequestSerializer(
            data=request.data,
            partial=True,
            context={"is_staff": False}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = UserService.update_citizen(
            actor=request.user,
            user_number=user_number,
            fields=validated_data
        )

        return DomainResultResponse(result).respond(
            success_status_code=status.HTTP_200_OK,
        )
