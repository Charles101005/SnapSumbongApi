from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.decorators import api_view

from shared.results import DomainResultResponse
from apps.accounts.services import UserService
from shared.authorization import AllPermissions
from shared.authorization.decorators import require_perm
from apps.accounts.serializers.response.profile_serializer import (
    GetProfileResponseSerializer,
    GetProfileImageSignatureResponseSerializer
)
from apps.accounts.serializers.request.profile_serializer import (
    ChangePasswordRequestSerializer,
    UpdateProfileRequestSerializer
)


@api_view(['GET'])
@require_perm(AllPermissions.USERS.UPDATE_OWN)
def profile_image_signature_view(request: Request) -> Response:
    result = UserService.get_profile_image_upload_credentials(request.user)

    return DomainResultResponse(result).respond(
        serializer_class=GetProfileImageSignatureResponseSerializer,
        success_status_code=status.HTTP_200_OK,
    )


class ProfileView(APIView):
    @require_perm(AllPermissions.USERS.READ_OWN)
    def get(self, request: Request) -> Response:
        serializer = GetProfileResponseSerializer(request.user)

        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @require_perm(AllPermissions.USERS.UPDATE_OWN)
    def patch(self, request: Request) -> Response:
        serializer = UpdateProfileRequestSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = UserService.update_profile(
            user=request.user,
            fields=validated_data
        )

        return DomainResultResponse(result).respond(
            success_status_code=status.HTTP_200_OK,
        )


@api_view(['POST'])
@require_perm(AllPermissions.USERS.UPDATE_OWN)
def change_password(request: Request) -> Response:
    serializer = ChangePasswordRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    validated_data = serializer.validated_data
    result = UserService.authenticated_change_password(
        user=request.user,
        current_refresh_token=request.COOKIES.get('refresh'),
        current_password=validated_data['current_password'],
        new_password=validated_data['new_password'],
    )

    return DomainResultResponse(result).respond(
        success_status_code=status.HTTP_200_OK
    )

@api_view(['POST'])
@require_perm(AllPermissions.USERS.DEACTIVATE_OWN)
def deactivate_account_view(request: Request) -> Response:
    result = UserService.deactivate_account(request.user)

    return DomainResultResponse(result).respond(
        success_status_code=status.HTTP_200_OK,
    )