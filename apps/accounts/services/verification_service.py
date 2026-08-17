import secrets
import string
from datetime import datetime

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from apps.accounts.models import VerificationRequest
from apps.accounts.exceptions.verification_exception import (
VerificationNotFoundError,
VerificationExpiredError,
VerificationAttemptsExceededError,
InvalidVerificationOTPError,
OTPResendLimitExceededError,
OTPResendCooldownActiveError
)


class VerificationService:
    @staticmethod
    def _config():
        return settings.VERIFICATION_REQUEST_CONFIG

    @staticmethod
    def _hash_otp(otp: str) -> str:
        return make_password(otp)

    @staticmethod
    def _send_otp(email: str, purpose: str, otp: str) -> None:
        # TODO: Connect to Email Integration
        print(f"{email=}\n{purpose=}\n{otp=}")

    @staticmethod
    def _generate_otp() -> str:
        length: int = VerificationService._config()['OTP_LENGTH']
        digits: str = string.digits

        return ''.join(secrets.choice(digits) for _ in range(length))

    @staticmethod
    def _expires_at(now) -> datetime:
        lifetime = VerificationService._config()['VERIFICATION_REQUEST_LIFETIME']

        return now + lifetime

    @staticmethod
    def create(
            email: str,
            purpose: str,
            payload: dict
    ) -> VerificationRequest:
        VerificationRequest.objects.delete_expired()

        now = timezone.now()
        expires_at = VerificationService._expires_at(now)

        otp = VerificationService._generate_otp()
        otp_hash = VerificationService._hash_otp(otp)

        verification = VerificationRequest.objects.get_active_or_none(email=email, purpose=purpose)

        if verification:
            verification.otp_hash = otp_hash
            verification.payload = payload

            verification.attempts = 0
            verification.resend_count = 0

            verification.expires_at = expires_at
            verification.last_sent_at = now

            verification.save(
                update_fields=[
                    'otp_hash',
                    'payload',
                    'attempts',
                    'resend_count',
                    'expires_at',
                    'last_sent_at',
                ]
            )

        else:
            verification = VerificationRequest.objects.create(
                email=email,
                purpose=purpose,
                otp_hash=otp_hash,
                payload=payload,

                expires_at=expires_at,
                last_sent_at=now
            )

        VerificationService._send_otp(
                email=email,
                purpose=purpose,
                otp=otp
        )

        return verification

    @staticmethod
    def verify(
            email: str,
            purpose: str,
            otp: str
    ) -> VerificationRequest:
        config = VerificationService._config()

        verification = VerificationRequest.objects.get_active_or_none(email=email, purpose=purpose)

        if verification is None:
            raise VerificationNotFoundError()

        if verification.expires_at <= timezone.now():
            verification.delete()
            raise VerificationExpiredError()

        if verification.attempts >= config['MAX_ATTEMPTS']:
            raise VerificationAttemptsExceededError()

        if not check_password(otp, verification.otp_hash):
            verification.attempts += 1
            verification.save(update_fields=['attempts'])
            raise InvalidVerificationOTPError()

        return verification

    @staticmethod
    def resend(
            email: str,
            purpose: str,
    ) -> VerificationRequest:
        verification = VerificationRequest.objects.get_active_or_none(email=email, purpose=purpose)

        if verification is None:
            raise VerificationNotFoundError()

        now = timezone.now()

        if verification.expires_at <= now:
            verification.delete()
            raise VerificationExpiredError()

        config = VerificationService._config()

        if verification.resend_count >= config['MAX_RESENDS']:
            verification.delete()
            raise OTPResendLimitExceededError()

        if now < verification.last_sent_at + config['RESEND_COOLDOWN']:
            raise OTPResendCooldownActiveError()

        otp = VerificationService._generate_otp()
        otp_hash = VerificationService._hash_otp(otp)

        verification.otp_hash = otp_hash
        verification.attempts = 0
        verification.resend_count += 1
        verification.expires_at = VerificationService._expires_at(now)
        verification.last_sent_at = now

        verification.save(
            update_fields=[
                'otp_hash',
                'attempts',
                'resend_count',
                'expires_at',
                'last_sent_at',
            ]
        )

        VerificationService._send_otp(
                email=email,
                purpose=purpose,
                otp=otp
        )

        return verification
