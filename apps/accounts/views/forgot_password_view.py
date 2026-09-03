from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from apps.accounts.services import ForgotPasswordService
from shared.results import DomainResultResponse
from apps.accounts.serializers.request.verification_serializer import (
VerifyOTPCodeRequestSerializer,
ResendOTPCodeRequestSerializer
)
from apps.accounts.serializers.response.verification_serializer import VerificationSessionCreationResponseSerializer
from apps.accounts.serializers.request.forgot_password_serializer import (
ForgotPasswordRequestSerializer,
ResetPasswordRequestSerializer
)
from apps.accounts.serializers.response.forgot_password_serializer import (
VerifyForgotPasswordResponseSerializer,
ResetPasswordResponseSerializer
)
from shared.views import BrowsableJSONViewMixin


class ForgotPasswordView(APIView, BrowsableJSONViewMixin):
    serializer_class = ForgotPasswordRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        result = ForgotPasswordService.request_reset_password(validated_data['email'])

        return DomainResultResponse(result).respond(
            success_status_code=status.HTTP_200_OK,
            success_data_override={
                "detail": f"Verification code has been sent to {validated_data['email']}",
                "email": validated_data['email']
            }
        )


class VerifyForgotPasswordView(APIView, BrowsableJSONViewMixin):
    serializer_class = VerifyOTPCodeRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = VerifyOTPCodeRequestSerializer(data=request.data)
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


class ResendForgotPasswordVerificationCodeView(APIView, BrowsableJSONViewMixin):
    serializer_class = ResendOTPCodeRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = ResendOTPCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        verification = ForgotPasswordService.resend_verification_code(validated_data['email'])

        return DomainResultResponse(verification).respond(
            serializer_class=VerificationSessionCreationResponseSerializer,
            success_status_code=status.HTTP_200_OK
        )


class ResetPasswordView(APIView, BrowsableJSONViewMixin):
    serializer_class = ResetPasswordRequestSerializer
    permission_classes = [AllowAny]

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