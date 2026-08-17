from django.contrib.auth.hashers import make_password

from apps.accounts.models import Users, VerificationRequest
from .user_service import UserService
from .verification_service import VerificationService
from apps.accounts.exceptions.user_exception import UserAlreadyExistsError


class RegisterService:
    @staticmethod
    def register_temp_user(
            email: str,
            password: str,
            last_name: str,
            first_name: str,
            middle_name: str|None = None,
    ) -> VerificationRequest:
        if Users.objects.filter(email=email).exists():
            raise UserAlreadyExistsError()

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
    def verify_temp_user_and_create_user(
            email: str,
            otp: str
    ) -> Users :
        verification: VerificationRequest = VerificationService.verify(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.REGISTRATION,
            otp=otp
        )

        payload: dict = verification.payload

        user = UserService.create_verified_citizen(
            email=email,
            password_hash=payload['password_hash'],
            last_name=payload['last_name'],
            first_name=payload['first_name'],
            middle_name=payload['middle_name'],
        )

        verification.delete()

        return user

    @staticmethod
    def resend_verification_code(email: str) -> VerificationRequest:
        return VerificationService.resend(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.REGISTRATION,
        )