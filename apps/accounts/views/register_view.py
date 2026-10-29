from django.utils.decorators import method_decorator
from django.middleware.csrf import rotate_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.services import RegisterService
from shared.results import DomainResultResponse
from apps.accounts.serializers.request.verification_serializer import (
    VerifyOTPCodeRequestSerializer,
    ResendOTPCodeRequestSerializer
)
from apps.accounts.serializers.response.verification_serializer import VerificationSessionCreationResponseSerializer
from apps.accounts.serializers.request.register_serializer import RegistrationRequestSerializer
from apps.accounts.serializers.response.register_serializer import VerifyRegistrationResponseSerializer
from shared.ratelimit import rate_limit, StrictRateLimit
from .auth_view import set_refresh_cookie



class RegistrationView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(StrictRateLimit)
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
            serializer_class=VerificationSessionCreationResponseSerializer,
            success_status_code=status.HTTP_201_CREATED,
        )


@method_decorator(ensure_csrf_cookie, name='dispatch')
class VerifyRegistrationView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(StrictRateLimit)
    def post(self, request: Request) -> Response:
        serializer = VerifyOTPCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data: dict = serializer.validated_data
        result = RegisterService.verify_temp_user_and_create_user(
            email=validated_data['email'],
            otp=validated_data['otp'],
        )

        if not result.is_success:
            return DomainResultResponse(result).respond(
                serializer_class=VerifyRegistrationResponseSerializer,
                success_status_code=status.HTTP_201_CREATED,
            )

        rotate_token(request)

        user = result.value
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        response = DomainResultResponse(result).respond(
            serializer_class=VerifyRegistrationResponseSerializer,
            success_status_code=status.HTTP_201_CREATED,
            serializer_context={"access": access},
        )
        set_refresh_cookie(response, str(refresh))

        return response


class ResendRegisterVerificationCodeView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(StrictRateLimit)
    def post(self, request: Request) -> Response:
        serializer = ResendOTPCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data: dict = serializer.validated_data
        verification = RegisterService.resend_verification_code(email=validated_data['email'])

        return DomainResultResponse(verification).respond(
            serializer_class=VerificationSessionCreationResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )
