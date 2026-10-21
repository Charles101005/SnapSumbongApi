import hashlib
import hmac
import secrets
import string
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from apps.accounts.models import VerificationRequest, Users
from apps.accounts.exceptions.verification_exception import VerificationNotFoundException
from shared.results import DomainResult
from external.email import EmailService
from apps.accounts.domain_errors.verification_error import (
        VerificationInProgressError,
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
    def _resolve_first_name(*, email: str, purpose: str, payload: dict) -> str:
        # A REGISTRATION OTP is sent before the account exists -- the name
        # only lives in the temp verification payload. Every other purpose
        # belongs to an existing account, so read it from the user row.
        if purpose == VerificationRequest.VerificationPurpose.REGISTRATION:
            return payload.get('first_name') or "there"

        user = Users.objects.get_by_active_email_or_none(email=email)
        return user.first_name if user else "there"

    @staticmethod
    def _send_otp(*, email: str, purpose: str, otp: str, first_name: str) -> None:
        expiry_minutes = int(
            VerificationService._config()['VERIFICATION_REQUEST_LIFETIME'].total_seconds() // 60
        )

        send_method = {
            VerificationRequest.VerificationPurpose.REGISTRATION:
                EmailService.send_registration_otp,
            VerificationRequest.VerificationPurpose.FORGOT_PASSWORD:
                EmailService.send_password_reset_otp,
            VerificationRequest.VerificationPurpose.EMAIL_CHANGE:
                EmailService.send_email_change_otp,
        }[purpose]

        send_method(
            to_email=email,
            to_first_name=first_name,
            otp_code=otp,
            expiry_minutes=expiry_minutes,
        )

    @staticmethod
    def _generate_otp() -> str:
        length: int = VerificationService._config()['OTP_LENGTH']
        digits: str = string.digits

        return ''.join(secrets.choice(digits) for _ in range(length))

    @staticmethod
    def expires_at(now: datetime) -> datetime:
        lifetime = VerificationService._config()['VERIFICATION_REQUEST_LIFETIME']

        return now + lifetime

    @staticmethod
    def generate_reset_token_and_hash() -> tuple[str, str]:
        reset_token = secrets.token_urlsafe(32)

        reset_token_hash = hashlib.sha256(
            reset_token.encode('utf-8')
        ).hexdigest()

        return reset_token, reset_token_hash

    @staticmethod
    def verify_reset_token(*, provided_token: str, correct_token_hash: str) -> bool:
        provided_token_hash = hashlib.sha256(
            provided_token.encode('utf-8')
        ).hexdigest()

        return hmac.compare_digest(provided_token_hash, correct_token_hash)

    @staticmethod
    @transaction.atomic
    def create(
            *,
            email: str,
            purpose: str,
            payload: dict
    ) -> DomainResult[VerificationRequest]:
        now = timezone.now()
        expires_at = VerificationService.expires_at(now)

        verification, created = VerificationRequest.objects.select_for_update().get_or_create(
            email=email,
            purpose=purpose,
            defaults={
                'otp_hash': '',
                'payload': {},
                'attempts': 0,
                'resend_count': 0,
                'expires_at': expires_at,
                'last_sent_at': now,
            }
        )

        if not created and verification.expires_at > now:
            return DomainResult.error(VerificationInProgressError)

        otp = VerificationService._generate_otp()
        otp_hash = VerificationService._hash_otp(otp)

        verification.otp_hash = otp_hash
        verification.payload = payload

        verification.expires_at = expires_at
        verification.last_sent_at = now

        if not created:
            verification.attempts = 0
            verification.resend_count = 0

        verification.save(update_fields=[
            'otp_hash',
            'payload',
            'attempts',
            'resend_count',
            'expires_at',
            'last_sent_at',
        ])

        transaction.on_commit(
            lambda: VerificationService._send_otp(
                email=email,
                purpose=purpose,
                otp=otp,
                first_name=VerificationService._resolve_first_name(
                    email=email,
                    purpose=purpose,
                    payload=payload
                ),
        ))

        return DomainResult.success(verification)

    @staticmethod
    @transaction.atomic
    def verify(
            *,
            email: str,
            purpose: str,
            otp: str
    ) -> DomainResult[VerificationRequest]:
        config = VerificationService._config()

        verification = VerificationRequest.objects.get_for_update_or_none(email=email, purpose=purpose)

        if verification is None:
            raise VerificationNotFoundException()

        resends_remaining = max(0, config['MAX_RESENDS'] - verification.resend_count)

        if verification.expires_at <= timezone.now():
            return DomainResult.error(VerificationExpiredError.with_meta(
                meta={
                    "expired_at": verification.expires_at.isoformat(),
                    "resends_remaining": resends_remaining,
                }
            ))

        if verification.attempts >= config['MAX_ATTEMPTS']:
            return DomainResult.error(VerificationAttemptsExceededError.with_meta(
                meta={
                    "resends_remaining": resends_remaining,
                }
            ))

        if not check_password(otp, verification.otp_hash):
            verification.attempts += 1
            verification.save(update_fields=['attempts'])

            return DomainResult.error(InvalidVerificationOTPError.with_meta(
                meta={
                    "attempts_remaining": max(0, config['MAX_ATTEMPTS'] - verification.attempts),
                    "max_attempts_allowed": config['MAX_ATTEMPTS'],
                }
            ))

        return DomainResult.success(verification)

    @staticmethod
    @transaction.atomic
    def resend(
            *,
            email: str,
            purpose: str,
    ) -> DomainResult[VerificationRequest]:
        verification = VerificationRequest.objects.get_for_update_or_none(email=email, purpose=purpose)

        if verification is None:
            raise VerificationNotFoundException()

        config = VerificationService._config()

        if verification.resend_count >= config['MAX_RESENDS']:
            verification.delete()
            return DomainResult.error(OTPResendLimitExceededError.with_meta(
                meta={
                    "next_action": "RESTART_VERIFICATION"
                }
            ))

        now = timezone.now()
        next_allowed_resend = verification.last_sent_at + config['RESEND_COOLDOWN']

        if now < next_allowed_resend:
            time_remaining = int((next_allowed_resend - now).total_seconds())

            return DomainResult.error(OTPResendCooldownActiveError.with_meta(
                meta={
                    'retry_after_seconds': max(1, time_remaining)
                }
            ))

        otp = VerificationService._generate_otp()
        otp_hash = VerificationService._hash_otp(otp)

        verification.otp_hash = otp_hash
        verification.attempts = 0
        verification.resend_count += 1
        verification.expires_at = VerificationService.expires_at(now)
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

        transaction.on_commit(
            lambda: VerificationService._send_otp(
                email=email,
                purpose=purpose,
                otp=otp,
                first_name=VerificationService._resolve_first_name(
                    email=email,
                    purpose=purpose,
                    payload=verification.payload
                ),
        ))

        return DomainResult.success(verification)