from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView

from shared.results import DomainResultResponse
from shared.authorization import AllPermissions
from shared.authorization.decorators import require_perm, require_any_perms
from shared.ratelimit import rate_limit, StandardRateLimit
from apps.accounts.services.moderation_service import ModerationService
from apps.accounts.serializers.request.moderation_serializer import (
    WarnCitizenRequestSerializer,
    BanCitizenRequestSerializer,
    UnbanCitizenRequestSerializer,
)
from apps.accounts.serializers.response.moderation_serializer import (
    CitizenWarningsResponseSerializer,
    ModerationSummaryResponseSerializer,
)


class WarnCitizenView(APIView):
    @rate_limit(StandardRateLimit)
    @require_perm(AllPermissions.USERS.WARN)
    def post(self, request: Request, user_number: str) -> Response:
        serializer = WarnCitizenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        result = ModerationService.issue_warning(
            actor=request.user,
            user_number=user_number,
            reason=validated["reason"],
            report_number=validated.get("report_number") or None,
        )

        return DomainResultResponse(result).respond(
            success_status_code=status.HTTP_201_CREATED,
        )


class BanCitizenView(APIView):
    @rate_limit(StandardRateLimit)
    @require_perm(AllPermissions.USERS.DEACTIVATE_ANY)
    def post(self, request: Request, user_number: str) -> Response:
        serializer = BanCitizenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        result = ModerationService.ban_citizen(
            actor=request.user,
            user_number=user_number,
            reason=validated["reason"],
            report_number=validated.get("report_number") or None,
        )

        return DomainResultResponse(result).respond(
            success_status_code=status.HTTP_200_OK,
        )


class UnbanCitizenView(APIView):
    @rate_limit(StandardRateLimit)
    @require_perm(AllPermissions.USERS.ACTIVATE_ANY)
    def post(self, request: Request, user_number: str) -> Response:
        serializer = UnbanCitizenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        result = ModerationService.unban_citizen(
            actor=request.user,
            user_number=user_number,
            reason=validated["reason"],
        )

        return DomainResultResponse(result).respond(
            success_status_code=status.HTTP_200_OK,
        )


class MyWarningsView(APIView):
    @require_perm(AllPermissions.USERS.READ_OWN)
    def get(self, request: Request) -> Response:
        result = ModerationService.get_citizen_warnings(user=request.user)

        return DomainResultResponse(result).respond(
            serializer_class=CitizenWarningsResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )


class MyModerationSummaryView(APIView):
    @require_perm(AllPermissions.USERS.READ_OWN)
    def get(self, request: Request) -> Response:
        result = ModerationService.get_moderation_summary(user=request.user)

        return DomainResultResponse(result).respond(
            serializer_class=ModerationSummaryResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )


class CitizenWarningsView(APIView):
    @require_any_perms(
        AllPermissions.USERS.READ_ALL,
        AllPermissions.USERS.WARN,
    )
    def get(self, request: Request, user_number: str) -> Response:
        result = ModerationService.get_warnings_for_user(user_number=user_number)

        return DomainResultResponse(result).respond(
            serializer_class=CitizenWarningsResponseSerializer,
            success_status_code=status.HTTP_200_OK,
        )
