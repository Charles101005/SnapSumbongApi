from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.accounts.models import Users, VerificationRequest
from .user_service import UserService
from .verification_service import VerificationService
from shared.results import DomainResult


class RegisterService:
    @staticmethod
    def register_temp_user(
            *,
            email: str,
            password: str,
            last_name: str,
            first_name: str,
            middle_name: str|None = None,
    ) -> DomainResult[VerificationRequest]:

        payload: dict = {
            'password_hash': make_password(password),
            'last_name': last_name,
            'first_name': first_name,
            'middle_name': middle_name,
        }

        return VerificationService.create(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.REGISTRATION,
            payload=payload,
        )

    @staticmethod
    @transaction.atomic
    def verify_temp_user_and_create_user(
            *,
            email: str,
            otp: str
    ) -> DomainResult[Users] :
        verification_result: DomainResult[VerificationRequest] = VerificationService.verify(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.REGISTRATION,
            otp=otp
        )

        if not verification_result.is_success:
            return DomainResult.error(verification_result.error)

        payload: dict = verification_result.value.payload

        user: DomainResult[Users] = UserService.create_verified_citizen(
            email=email,
            password_hash=payload['password_hash'],
            last_name=payload['last_name'],
            first_name=payload['first_name'],
            middle_name=payload['middle_name'],
        )

        verification_result.value.delete()

        return DomainResult.success(user.value)

    @staticmethod
    def resend_verification_code(email: str) -> DomainResult[VerificationRequest]:
        return VerificationService.resend(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.REGISTRATION,
        )