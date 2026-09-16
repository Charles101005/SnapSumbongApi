from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Users, VerificationRequest
from apps.accounts.services import UserService, AuthService
from .verification_service import VerificationService
from shared.results import DomainResult
from apps.accounts.domain_errors.forgot_password_error import PasswordResetInvalidError
from apps.accounts.exceptions.forgot_password_exception import ForgotPasswordRequestNotFoundException


class ForgotPasswordService:
    @staticmethod
    def request_reset_password(email: str) -> DomainResult[VerificationRequest|None]:
        user: Users = Users.objects.get_by_active_email_or_none(email=email)

        if user is None:
            return DomainResult.success(None)

        return VerificationService.create(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.FORGOT_PASSWORD,
            payload={},
        )

    @staticmethod
    @transaction.atomic
    def verify_otp(
            *,
            email: str,
            otp: str,
    ) -> DomainResult[dict[str, str]]:
        verification, error = VerificationService.verify(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.FORGOT_PASSWORD,
            otp=otp,
        ).unwrap()

        if error: return DomainResult.error(error)

        reset_token, reset_token_hash = VerificationService.generate_reset_token_and_hash()

        verification.payload = {
            **verification.payload,
            "reset_token_hash": reset_token_hash,
        }

        verification.otp_hash = None
        verification.expires_at = VerificationService.expires_at(timezone.now())

        verification.save(update_fields=[
            "otp_hash",
            "payload",
            "expires_at"
        ])

        return DomainResult.success({
            "email": email,
            "reset_token": reset_token,
        })

    @staticmethod
    def resend_verification_code(email: str) -> DomainResult[VerificationRequest]:
        return VerificationService.resend(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.FORGOT_PASSWORD
        )

    @staticmethod
    @transaction.atomic
    def reset_password(
            *,
            email: str,
            reset_token: str,
            new_password: str,
    ) -> DomainResult[Users]:
        verification = VerificationRequest.objects.get_password_reset_ready_or_none(email=email)

        if verification is None:
            raise ForgotPasswordRequestNotFoundException()

        if verification.expires_at <= timezone.now():
            verification.delete()
            return DomainResult.error(PasswordResetInvalidError)

        correct_token_hash = verification.payload.get("reset_token_hash")

        if correct_token_hash is None:
            verification.delete()
            return DomainResult.error(PasswordResetInvalidError)

        if not VerificationService.verify_reset_token(
            provided_token=reset_token,
            correct_token_hash=correct_token_hash
        ):
            return DomainResult.error(PasswordResetInvalidError)

        user, error = UserService.unauthenticated_change_password(
            email=email,
            new_password=new_password
        ).unwrap()

        if error: return DomainResult.error(error)

        AuthService.revoke_all_refresh_tokens(user=user)

        verification.delete()

        return DomainResult.success(user)