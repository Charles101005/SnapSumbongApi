from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView

from shared.results import DomainResultResponse
from shared.authorization import AllPermissions
from shared.authorization.decorators import require_perm, require_any_perms
from shared.pagination import SmallListPagination
from apps.accounts.services import UserService
from apps.accounts.serializers.request.user_serializer import (
    UserUpdateRequestSerializer,
    UserListRequestSerializer,
    CreateEmployeeRequestSerializer
)
from apps.accounts.serializers.response.user_serializer import (
    UserListResponseSerializer,
    UserDetailResponseSerializer,
    CreateEmployeeResponseSerializer
)

class EmployeeListView(APIView):
    @require_perm(AllPermissions.EMPLOYEES.READ_ALL)
    def get(self, request: Request) -> Response:
        serializer = UserListRequestSerializer(
            data=request.query_params,
            context={"is_staff": True}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = UserService.list_users(
            is_staff=True,
            query_filters=validated_data
        )

        return DomainResultResponse(result).respond_with_pagination(
            request=request,
            pagination_class=SmallListPagination,
            serializer_class=UserListResponseSerializer,
            serializer_context={"is_staff": True},
            success_status_code=status.HTTP_200_OK
        )

    @require_perm(AllPermissions.EMPLOYEES.CREATE)
    def post(self, request: Request) -> Response:
        serializer = CreateEmployeeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = UserService.create_staff(
            email=validated_data["email"],
            role_id=validated_data["role_id"],
            last_name=validated_data["last_name"],
            first_name=validated_data["first_name"],
            middle_name=validated_data["middle_name"],
            contact_number=validated_data["contact_number"],
            birth_date=validated_data["birth_date"],
            gender=validated_data["gender"],
            street_address=validated_data["street_address"],
            region_code=validated_data["region_code"],
            province_code=validated_data["province_code"],
            city_code=validated_data["city_code"],
            barangay_code=validated_data["barangay_code"],
        )

        return DomainResultResponse(result).respond(
            serializer_class=CreateEmployeeResponseSerializer,
            success_status_code=status.HTTP_201_CREATED
        )


class EmployeeDetailView(APIView):
    @require_perm(AllPermissions.EMPLOYEES.READ_ALL)
    def get(self, request: Request, user_number: str) -> Response:
        result = UserService.get_user(
            user_number=user_number,
            is_staff=True
        )

        return DomainResultResponse(result).respond(
            serializer_class=UserDetailResponseSerializer,
            success_status_code=status.HTTP_200_OK
        )

    @require_any_perms(
        AllPermissions.EMPLOYEES.UPDATE_ANY,
        AllPermissions.EMPLOYEES.ASSIGN_ROLE,
        AllPermissions.EMPLOYEES.ACTIVATE_ANY,
        AllPermissions.EMPLOYEES.DEACTIVATE_ANY,
    )
    def patch(self, request: Request, user_number: str) -> Response:
        serializer = UserUpdateRequestSerializer(
            data=request.data,
            partial=True,
            context={"is_staff": True}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = UserService.update_staff(
            actor=request.user,
            user_number=user_number,
            fields=validated_data
        )

        return DomainResultResponse(result).respond(
            success_status_code=status.HTTP_200_OK
        )
