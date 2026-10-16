from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils import timezone

from apps.accounts.domain_errors.verification_error import (
    InvalidVerificationOTPError,
    OTPResendCooldownActiveError,
    OTPResendLimitExceededError,
    VerificationAttemptsExceededError,
    VerificationExpiredError,
    VerificationInProgressError,
)
from apps.accounts.exceptions.verification_exception import VerificationNotFoundException
from apps.accounts.models import VerificationRequest
from apps.accounts.services import VerificationService
from apps.accounts.tests.factories import VerificationRequestFactory


CONFIG = settings.VERIFICATION_REQUEST_CONFIG
REGISTRATION = VerificationRequest.VerificationPurpose.REGISTRATION
FORGOT_PASSWORD = VerificationRequest.VerificationPurpose.FORGOT_PASSWORD


@pytest.mark.django_db
class TestGenerateOtpAndHash:
    def test_generate_otp_uses_configured_length_and_digits_only(self):
        otp = VerificationService._generate_otp()

        assert len(otp) == CONFIG['OTP_LENGTH']
        assert otp.isdigit()

    def test_hash_otp_is_verifiable(self):
        otp = '1234'
        otp_hash = VerificationService._hash_otp(otp)

        assert check_password(otp, otp_hash)


class TestResetToken:
    def test_generate_reset_token_and_hash_round_trip(self):
        reset_token, reset_token_hash = VerificationService.generate_reset_token_and_hash()

        assert VerificationService.verify_reset_token(
            provided_token=reset_token,
            correct_token_hash=reset_token_hash,
        ) is True

    def test_verify_reset_token_rejects_wrong_token(self):
        _, reset_token_hash = VerificationService.generate_reset_token_and_hash()

        assert VerificationService.verify_reset_token(
            provided_token='wrong-token',
            correct_token_hash=reset_token_hash,
        ) is False


class TestExpiresAt:
    def test_expires_at_adds_configured_lifetime(self):
        now = timezone.now()

        assert VerificationService.expires_at(now) == now + CONFIG['VERIFICATION_REQUEST_LIFETIME']


@pytest.mark.django_db
class TestCreate:
    def test_creates_new_verification(self, mocker):
        mocker.patch.object(VerificationService, '_generate_otp', return_value='1234')

        result = VerificationService.create(
            email='new@email.com',
            purpose=REGISTRATION,
            payload={'key': 'value'},
        )

        assert result.is_success
        verification = result.value
        assert verification.email == 'new@email.com'
        assert verification.purpose == REGISTRATION
        assert check_password('1234', verification.otp_hash)
        assert verification.payload == {'key': 'value'}
        assert verification.attempts == 0
        assert verification.resend_count == 0

    def test_returns_error_when_active_verification_exists(self):
        VerificationRequestFactory(
            email='pending@email.com',
            purpose=REGISTRATION,
            expires_at=timezone.now() + timedelta(minutes=1),
        )

        result = VerificationService.create(
            email='pending@email.com',
            purpose=REGISTRATION,
            payload={},
        )

        assert result.is_success is False
        assert result.error is VerificationInProgressError

    def test_resets_expired_verification_and_succeeds(self, mocker):
        mocker.patch.object(VerificationService, '_generate_otp', return_value='5678')
        VerificationRequestFactory(
            email='expired@email.com',
            purpose=REGISTRATION,
            attempts=2,
            resend_count=1,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        result = VerificationService.create(
            email='expired@email.com',
            purpose=REGISTRATION,
            payload={'new': 'payload'},
        )

        assert result.is_success
        verification = result.value
        assert verification.attempts == 0
        assert verification.resend_count == 0
        assert check_password('5678', verification.otp_hash)
        assert verification.payload == {'new': 'payload'}
        assert verification.expires_at > timezone.now()

    def test_is_scoped_by_purpose(self, mocker):
        mocker.patch.object(VerificationService, '_generate_otp', return_value='1234')
        VerificationRequestFactory(
            email='scoped@email.com',
            purpose=REGISTRATION,
            expires_at=timezone.now() + timedelta(minutes=1),
        )

        result = VerificationService.create(
            email='scoped@email.com',
            purpose=FORGOT_PASSWORD,
            payload={},
        )

        assert result.is_success


@pytest.mark.django_db
class TestVerify:
    def test_raises_when_no_verification_found(self):
        with pytest.raises(VerificationNotFoundException):
            VerificationService.verify(email='none@email.com', purpose=REGISTRATION, otp='1234')

    def test_returns_expired_error_with_meta(self):
        VerificationRequestFactory(
            email='expired@email.com',
            purpose=REGISTRATION,
            resend_count=1,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        result = VerificationService.verify(
            email='expired@email.com',
            purpose=REGISTRATION,
            otp='1234',
        )

        assert result.is_success is False
        assert result.error.error_code == VerificationExpiredError.error_code
        assert 'expired_at' in result.error.meta
        assert result.error.meta['resends_remaining'] == CONFIG['MAX_RESENDS'] - 1

    def test_returns_attempts_exceeded_error(self):
        VerificationRequestFactory(
            email='locked@email.com',
            purpose=REGISTRATION,
            attempts=CONFIG['MAX_ATTEMPTS'],
        )

        result = VerificationService.verify(
            email='locked@email.com',
            purpose=REGISTRATION,
            otp='1234',
        )

        assert result.is_success is False
        assert result.error.error_code == VerificationAttemptsExceededError.error_code
        assert result.error.meta['resends_remaining'] == CONFIG['MAX_RESENDS']

    def test_invalid_otp_increments_attempts_and_returns_meta(self):
        verification = VerificationRequestFactory(
            email='wrong@email.com',
            purpose=REGISTRATION,
            attempts=1,
        )

        result = VerificationService.verify(
            email='wrong@email.com',
            purpose=REGISTRATION,
            otp='9999',
        )

        assert result.is_success is False
        assert result.error.error_code == InvalidVerificationOTPError.error_code
        assert result.error.meta['max_attempts_allowed'] == CONFIG['MAX_ATTEMPTS']

        verification.refresh_from_db()
        assert verification.attempts == 2
        assert result.error.meta['attempts_remaining'] == CONFIG['MAX_ATTEMPTS'] - 2

    def test_correct_otp_succeeds(self, mocker):
        mocker.patch.object(VerificationService, '_generate_otp', return_value='4321')
        VerificationService.create(email='ok@email.com', purpose=REGISTRATION, payload={})

        result = VerificationService.verify(email='ok@email.com', purpose=REGISTRATION, otp='4321')

        assert result.is_success
        assert result.value.email == 'ok@email.com'

    def test_verify_is_scoped_by_purpose(self, mocker):
        mocker.patch.object(VerificationService, '_generate_otp', return_value='4321')
        VerificationService.create(email='scoped@email.com', purpose=REGISTRATION, payload={})

        with pytest.raises(VerificationNotFoundException):
            VerificationService.verify(email='scoped@email.com', purpose=FORGOT_PASSWORD, otp='4321')


@pytest.mark.django_db
class TestResend:
    def test_raises_when_no_verification_found(self):
        with pytest.raises(VerificationNotFoundException):
            VerificationService.resend(email='none@email.com', purpose=REGISTRATION)

    def test_deletes_verification_when_resend_limit_exceeded(self):
        verification = VerificationRequestFactory(
            email='limited@email.com',
            purpose=REGISTRATION,
            resend_count=CONFIG['MAX_RESENDS'],
            last_sent_at=timezone.now() - timedelta(minutes=5),
        )

        result = VerificationService.resend(email='limited@email.com', purpose=REGISTRATION)

        assert result.is_success is False
        assert result.error.error_code == OTPResendLimitExceededError.error_code
        assert result.error.meta['next_action'] == 'RESTART_VERIFICATION'
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_returns_cooldown_error_with_retry_after(self):
        VerificationRequestFactory(
            email='cooldown@email.com',
            purpose=REGISTRATION,
            last_sent_at=timezone.now(),
        )

        result = VerificationService.resend(email='cooldown@email.com', purpose=REGISTRATION)

        assert result.is_success is False
        assert result.error.error_code == OTPResendCooldownActiveError.error_code
        assert result.error.meta['retry_after_seconds'] >= 1

    def test_successful_resend_resets_attempts_and_rotates_otp(self, mocker):
        mocker.patch.object(VerificationService, '_generate_otp', return_value='0000')
        verification = VerificationRequestFactory(
            email='resend@email.com',
            purpose=REGISTRATION,
            attempts=2,
            resend_count=0,
            last_sent_at=timezone.now() - timedelta(minutes=5),
            expires_at=timezone.now() - timedelta(minutes=4),
        )

        result = VerificationService.resend(email='resend@email.com', purpose=REGISTRATION)

        assert result.is_success
        verification.refresh_from_db()
        assert verification.attempts == 0
        assert verification.resend_count == 1
        assert check_password('0000', verification.otp_hash)
        assert verification.expires_at > timezone.now()
        assert verification.last_sent_at <= timezone.now()
