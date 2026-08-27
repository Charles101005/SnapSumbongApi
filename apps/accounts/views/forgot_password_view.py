from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.services import ForgotPasswordService
from shared.results import DomainResultResponse
from apps.accounts.serializers.request.forgot_password_serializer import (
ForgotPasswordRequestSerializer,
VerifyForgotPasswordRequestSerializer,
ResendForgotPasswordVerificationCodeRequestSerializer,
ResetPasswordRequestSerializer
)
from apps.accounts.serializers.response.forgot_password_serializer import (
ForgotPasswordResponseSerializer,
VerifyForgotPasswordResponseSerializer,
ResendForgotPasswordVerificationCodeResponseSerializer,
ResetPasswordResponseSerializer
)


class ForgotPasswordView(APIView):
    def post(self, request: Request) -> Response:
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        verification = ForgotPasswordService.request_reset_password(validated_data['email'])

        return DomainResultResponse(verification).respond(
            serializer_class=ForgotPasswordResponseSerializer,
            success_status_code=status.HTTP_201_CREATED
        )


class VerifyForgotPasswordView(APIView):
    def post(self, request: Request) -> Response:
        serializer = VerifyForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = ForgotPasswordService.verify_otp(
            email=validated_data['email'],
            otp=validated_data['otp'],
        )
        return DomainResultResponse(result).respond(
            serializer_class=VerifyForgotPasswordResponseSerializer,
            success_status_code=status.HTTP_200_OK
        )


class ResendForgotPasswordVerificationCodeView(APIView):
    def post(self, request: Request) -> Response:
        serializer = ResendForgotPasswordVerificationCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        verification = ForgotPasswordService.resend_verification_code(validated_data['email'])

        return DomainResultResponse(verification).respond(
            serializer_class=ResendForgotPasswordVerificationCodeResponseSerializer,
            success_status_code=status.HTTP_200_OK
        )


class ResetPasswordView(APIView):
    def post(self, request: Request) -> Response:
        serializer = ResetPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        user = ForgotPasswordService.reset_password(
            email=validated_data['email'],
            reset_token=validated_data['reset_token'],
            new_password=validated_data['new_password'],
        )

        return DomainResultResponse(user).respond(
            serializer_class=ResetPasswordResponseSerializer,
            success_status_code=status.HTTP_200_OK
        )