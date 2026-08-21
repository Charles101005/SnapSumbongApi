from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.services import RegisterService
from shared.results import DomainResultResponse
from apps.accounts.serializers.request.register_serializer import (
RegistrationRequestSerializer,
VerifyRegistrationRequestSerializer,
ResendVerificationCodeRequestSerializer
)
from apps.accounts.serializers.response.register_serializer import (
RegistrationResponseSerializer,
VerifyRegistrationResponseSerializer,
ResendVerificationCodeResponseSerializer
)


class RegistrationView(APIView):
    def post(self, request: Request) -> Response:
        serializer = RegistrationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data: dict = serializer.validated_data
        verification = RegisterService.register_temp_user(
            email=validated_data['email'],
            password=validated_data['password'],
            last_name=validated_data['last_name'],
            first_name=validated_data['first_name'],
            middle_name=validated_data['middle_name'],
        )

        return DomainResultResponse(verification).respond(
            serializer_class=RegistrationResponseSerializer,
            success_status_code=status.HTTP_201_CREATED,
        )


class VerifyRegistrationView(APIView):
    def post(self, request: Request) -> Response:
        serializer = VerifyRegistrationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data: dict = serializer.validated_data
        user = RegisterService.verify_temp_user_and_create_user(
            email=validated_data['email'],
            otp=validated_data['otp'],
        )

        return DomainResultResponse(user).respond(
            serializer_class=VerifyRegistrationResponseSerializer,
            success_status_code=status.HTTP_201_CREATED,
        )


class ResendRegisterVerificationCodeView(APIView):
    def post(self, request: Request) -> Response:
        serializer = ResendVerificationCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data: dict = serializer.validated_data
        verification = RegisterService.resend_verification_code(email=validated_data['email'])

        return DomainResultResponse(verification).respond(
            serializer_class=ResendVerificationCodeResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )
