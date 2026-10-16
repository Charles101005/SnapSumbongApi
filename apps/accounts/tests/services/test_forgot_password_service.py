from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.domain_errors.forgot_password_error import PasswordResetInvalidError
from apps.accounts.exceptions.forgot_password_exception import ForgotPasswordRequestNotFoundException
from apps.accounts.models import VerificationRequest
from apps.accounts.services import ForgotPasswordService, VerificationService
from apps.accounts.tests.factories import UserFactory, VerificationRequestFactory
from apps.accounts.tests.factories.verification_factory import TEST_OTP


FORGOT_PASSWORD = VerificationRequest.VerificationPurpose.FORGOT_PASSWORD


@pytest.mark.django_db
class TestRequestResetPassword:
    def test_known_email_creates_forgot_password_verification(self, citizen_role):
        user = UserFactory(role=citizen_role)

        result = ForgotPasswordService.request_reset_password(user.email)

        assert result.is_success
        verification = result.value
        assert verification.email == user.email
        assert verification.purpose == FORGOT_PASSWORD

    def test_unknown_email_returns_success_with_none(self):
        result = ForgotPasswordService.request_reset_password('unknown@email.com')

        assert result.is_success
        assert result.value is None
        assert not VerificationRequest.objects.filter(email='unknown@email.com').exists()

    def test_inactive_user_is_treated_as_unknown(self, citizen_role):
        user = UserFactory(role=citizen_role, is_active=False)

        result = ForgotPasswordService.request_reset_password(user.email)

        assert result.is_success
        assert result.value is None


@pytest.mark.django_db
class TestVerifyOtp:
    def _seed_otp_verification(self, email='reset@email.com', otp=TEST_OTP):
        from django.contrib.auth.hashers import make_password

        return VerificationRequestFactory(
            email=email,
            purpose=FORGOT_PASSWORD,
            otp_hash=make_password(otp),
            payload={},
        )

    def test_correct_otp_returns_reset_token_and_converts_session(self):
        verification = self._seed_otp_verification()

        result = ForgotPasswordService.verify_otp(email=verification.email, otp=TEST_OTP)

        assert result.is_success
        assert result.value['email'] == verification.email
        assert 'reset_token' in result.value

        verification.refresh_from_db()
        assert verification.otp_hash is None
        assert 'reset_token_hash' in verification.payload

    def test_wrong_otp_returns_error(self):
        verification = self._seed_otp_verification()

        result = ForgotPasswordService.verify_otp(email=verification.email, otp='9999')

        assert result.is_success is False
        assert result.error.error_code == 'INVALID_VERIFICATION_OTP'

        verification.refresh_from_db()
        assert verification.otp_hash is not None
        assert 'reset_token_hash' not in verification.payload


@pytest.mark.django_db
class TestResetPassword:
    def _seed_ready_verification(
            self,
            email='ready@email.com',
            *,
            expired=False,
            include_token_hash=True,
    ):
        reset_token, reset_token_hash = VerificationService.generate_reset_token_and_hash()
        verification = VerificationRequestFactory(
            email=email,
            purpose=FORGOT_PASSWORD,
            otp_hash=None,
            payload={'reset_token_hash': reset_token_hash} if include_token_hash else {},
            expires_at=(
                timezone.now() - timedelta(minutes=1) if expired
                else timezone.now() + timedelta(minutes=10)
            ),
        )
        return verification, reset_token

    def test_raises_when_no_ready_verification_exists(self):
        with pytest.raises(ForgotPasswordRequestNotFoundException):
            ForgotPasswordService.reset_password(
                email='none@email.com',
                reset_token='any-token',
                new_password='NewPassword123',
            )

    def test_expired_verification_is_deleted_and_rejected(self, citizen_role):
        user = UserFactory(role=citizen_role)
        verification, reset_token = self._seed_ready_verification(
            email=user.email,
            expired=True,
        )

        result = ForgotPasswordService.reset_password(
            email=user.email,
            reset_token=reset_token,
            new_password='NewPassword123',
        )

        assert result.is_success is False
        assert result.error.error_code == PasswordResetInvalidError.error_code
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_missing_token_hash_is_treated_as_no_ready_request(self, citizen_role):
        # get_password_reset_ready_or_none filters on payload__has_key
        # "reset_token_hash", so a payload without the key never counts as a
        # ready request and the service treats it as missing.
        user = UserFactory(role=citizen_role)
        verification, _ = self._seed_ready_verification(
            email=user.email,
            include_token_hash=False,
        )

        with pytest.raises(ForgotPasswordRequestNotFoundException):
            ForgotPasswordService.reset_password(
                email=user.email,
                reset_token='any-token',
                new_password='NewPassword123',
            )

        assert VerificationRequest.objects.filter(pk=verification.pk).exists()
        user.refresh_from_db()
        assert user.check_password('Password2005')

    def test_wrong_reset_token_is_rejected_and_session_kept(self, citizen_role):
        user = UserFactory(role=citizen_role)
        verification, _ = self._seed_ready_verification(email=user.email)

        result = ForgotPasswordService.reset_password(
            email=user.email,
            reset_token='wrong-token',
            new_password='NewPassword123',
        )

        assert result.is_success is False
        assert result.error.error_code == PasswordResetInvalidError.error_code
        assert VerificationRequest.objects.filter(pk=verification.pk).exists()
        user.refresh_from_db()
        assert user.check_password('Password2005')
        assert not user.check_password('NewPassword123')

    def test_valid_token_resets_password_revokes_tokens_and_cleans_up(self, citizen_role):
        user = UserFactory(role=citizen_role)
        outstanding_token = RefreshToken.for_user(user)
        verification, reset_token = self._seed_ready_verification(email=user.email)

        result = ForgotPasswordService.reset_password(
            email=user.email,
            reset_token=reset_token,
            new_password='NewPassword123',
        )

        assert result.is_success
        assert result.value.pk == user.pk

        user.refresh_from_db()
        assert user.check_password('NewPassword123')
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()
        assert BlacklistedToken.objects.filter(token__token=str(outstanding_token)).exists()
