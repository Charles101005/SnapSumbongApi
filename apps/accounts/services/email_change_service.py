from django.db import transaction, IntegrityError
from django.utils import timezone

from apps.accounts.models import Users, VerificationRequest
from apps.accounts.services.verification_service import VerificationService
from apps.accounts.exceptions.verification_exception import VerificationNotFoundException
from shared.results import DomainResult
from apps.accounts.domain_errors.email_change_error import (
    EmailSameAsCurrentError,
    EmailAlreadyTakenError,
    EmailChangeVerificationInvalidError,
)
from apps.accounts.domain_errors.verification_error import VerificationInProgressError


class EmailChangeService:
    @staticmethod
    def request_email_change(
            *,
            user: Users,
            new_email: str,
    ) -> DomainResult[VerificationRequest]:
        if new_email.lower() == user.email.lower():
            return DomainResult.error(EmailSameAsCurrentError)

        if Users.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
            return DomainResult.error(EmailAlreadyTakenError)

        pending = VerificationRequest.objects.filter(
            purpose=VerificationRequest.VerificationPurpose.EMAIL_CHANGE,
            payload__user_id=user.user_id,
            expires_at__gt=timezone.now(),
        ).first()

        if pending:
            return DomainResult.error(VerificationInProgressError)

        payload = {
            "user_id": user.user_id,
            "old_email": user.email,
            "new_email": new_email,
        }

        return VerificationService.create(
            email=new_email,
            purpose=VerificationRequest.VerificationPurpose.EMAIL_CHANGE,
            payload=payload,
        )

    @staticmethod
    @transaction.atomic
    def verify_email_change(
            *,
            user: Users,
            email: str,
            otp: str,
    ) -> DomainResult[Users]:
        verification, error = VerificationService.verify(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.EMAIL_CHANGE,
            otp=otp,
        ).unwrap()

        if error:
            return DomainResult.error(error)

        payload = verification.payload
        if payload.get("user_id") != user.user_id:
            verification.delete()
            return DomainResult.error(EmailChangeVerificationInvalidError)

        new_email = payload.get("new_email")
        if not new_email:
            verification.delete()
            return DomainResult.error(EmailChangeVerificationInvalidError)

        try:
            if Users.objects.select_for_update().filter(
                    email__iexact=new_email
            ).exclude(pk=user.pk).exists():
                verification.delete()
                return DomainResult.error(EmailAlreadyTakenError)

            user.email = new_email
            user.save(update_fields=["email", "updated_at"])
        except IntegrityError:
            verification.delete()
            return DomainResult.error(EmailAlreadyTakenError)

        verification.delete()

        return DomainResult.success(user)

    @staticmethod
    @transaction.atomic
    def resend_email_change(
            *,
            user: Users,
            email: str,
    ) -> DomainResult[VerificationRequest]:
        verification = VerificationRequest.objects.get_for_update_or_none(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.EMAIL_CHANGE,
        )

        if verification is None or verification.payload.get("user_id") != user.user_id:
            raise VerificationNotFoundException()

        return VerificationService.resend(
            email=email,
            purpose=VerificationRequest.VerificationPurpose.EMAIL_CHANGE,
        )
