from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.accounts.domain_errors.email_change_error import (
    EmailSameAsCurrentError,
    EmailAlreadyTakenError,
    EmailChangeVerificationInvalidError,
)
from apps.accounts.exceptions.verification_exception import VerificationNotFoundException
from apps.accounts.models import VerificationRequest
from apps.accounts.services import EmailChangeService, VerificationService
from apps.accounts.tests.factories import UserFactory, VerificationRequestFactory
from apps.accounts.tests.factories.verification_factory import TEST_OTP


EMAIL_CHANGE = VerificationRequest.VerificationPurpose.EMAIL_CHANGE


@pytest.mark.django_db
class TestRequestEmailChange:
    def test_creates_verification_with_payload(self, citizen_role):
        user = UserFactory(role=citizen_role)

        result = EmailChangeService.request_email_change(user=user, new_email='new@email.com')

        assert result.is_success
        verification = result.value
        assert verification.email == 'new@email.com'
        assert verification.purpose == EMAIL_CHANGE
        assert verification.payload['user_id'] == user.user_id
        assert verification.payload['old_email'] == user.email
        assert verification.payload['new_email'] == 'new@email.com'

    def test_same_email_returns_error(self, citizen_role):
        user = UserFactory(role=citizen_role)

        result = EmailChangeService.request_email_change(user=user, new_email=user.email)

        assert result.is_success is False
        assert result.error.error_code == EmailSameAsCurrentError.error_code

    def test_same_email_case_insensitive_returns_error(self, citizen_role):
        user = UserFactory(role=citizen_role, email='user@email.com')

        result = EmailChangeService.request_email_change(user=user, new_email='USER@email.com')

        assert result.is_success is False
        assert result.error.error_code == EmailSameAsCurrentError.error_code

    def test_taken_email_returns_error(self, citizen_role):
        user = UserFactory(role=citizen_role)
        other = UserFactory(role=citizen_role, email='taken@email.com')

        result = EmailChangeService.request_email_change(user=user, new_email='taken@email.com')

        assert result.is_success is False
        assert result.error.error_code == EmailAlreadyTakenError.error_code

    def test_taken_email_case_insensitive_returns_error(self, citizen_role):
        user = UserFactory(role=citizen_role)
        UserFactory(role=citizen_role, email='taken@email.com')

        result = EmailChangeService.request_email_change(user=user, new_email='TAKEN@email.com')

        assert result.is_success is False
        assert result.error.error_code == EmailAlreadyTakenError.error_code

    def test_pending_verification_blocks_new_request(self, citizen_role):
        user = UserFactory(role=citizen_role)
        EmailChangeService.request_email_change(user=user, new_email='new@email.com')

        result = EmailChangeService.request_email_change(user=user, new_email='other@email.com')

        assert result.is_success is False
        assert result.error.error_code == 'VERIFICATION_IN_PROGRESS'

    def test_expired_verification_is_replaced(self, citizen_role):
        user = UserFactory(role=citizen_role)
        VerificationRequestFactory(
            email='old_new@email.com',
            purpose=EMAIL_CHANGE,
            expires_at=timezone.now() - timedelta(minutes=1),
            payload={'user_id': user.user_id, 'new_email': 'old_new@email.com'},
        )

        result = EmailChangeService.request_email_change(user=user, new_email='new@email.com')

        assert result.is_success
        assert result.value.email == 'new@email.com'


@pytest.mark.django_db
class TestVerifyEmailChange:
    def _seed_verification(self, user, new_email, otp=TEST_OTP):
        return VerificationRequestFactory(
            email=new_email,
            purpose=EMAIL_CHANGE,
            otp_hash=make_password(otp),
            payload={
                'user_id': user.user_id,
                'old_email': user.email,
                'new_email': new_email,
            },
        )

    def test_correct_otp_updates_email_and_consumes_verification(self, citizen_role):
        user = UserFactory(role=citizen_role)
        verification = self._seed_verification(user, 'new@email.com')

        result = EmailChangeService.verify_email_change(
            user=user,
            email='new@email.com',
            otp=TEST_OTP,
        )

        assert result.is_success
        user.refresh_from_db()
        assert user.email == 'new@email.com'
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_wrong_otp_returns_error(self, citizen_role):
        user = UserFactory(role=citizen_role)
        verification = self._seed_verification(user, 'new@email.com')

        result = EmailChangeService.verify_email_change(
            user=user,
            email='new@email.com',
            otp='9999',
        )

        assert result.is_success is False
        assert result.error.error_code == 'INVALID_VERIFICATION_OTP'
        user.refresh_from_db()
        assert user.email != 'new@email.com'
        assert VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_mismatched_user_id_returns_invalid_error_and_deletes_verification(self, citizen_role):
        user = UserFactory(role=citizen_role)
        other = UserFactory(role=citizen_role)
        verification = self._seed_verification(user, 'new@email.com')

        result = EmailChangeService.verify_email_change(
            user=other,
            email='new@email.com',
            otp=TEST_OTP,
        )

        assert result.is_success is False
        assert result.error.error_code == EmailChangeVerificationInvalidError.error_code
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()
        user.refresh_from_db()
        assert user.email != 'new@email.com'

    def test_email_taken_at_verify_time_returns_error(self, citizen_role):
        user = UserFactory(role=citizen_role)
        verification = self._seed_verification(user, 'new@email.com')
        UserFactory(role=citizen_role, email='new@email.com')

        result = EmailChangeService.verify_email_change(
            user=user,
            email='new@email.com',
            otp=TEST_OTP,
        )

        assert result.is_success is False
        assert result.error.error_code == EmailAlreadyTakenError.error_code
        user.refresh_from_db()
        assert user.email != 'new@email.com'

    def test_expired_otp_returns_error(self, citizen_role):
        user = UserFactory(role=citizen_role)
        verification = VerificationRequestFactory(
            email='new@email.com',
            purpose=EMAIL_CHANGE,
            otp_hash=make_password(TEST_OTP),
            expires_at=timezone.now() - timedelta(minutes=1),
            payload={'user_id': user.user_id, 'new_email': 'new@email.com'},
        )

        result = EmailChangeService.verify_email_change(
            user=user,
            email='new@email.com',
            otp=TEST_OTP,
        )

        assert result.is_success is False
        assert result.error.error_code == 'VERIFICATION_EXPIRED'

    def test_unknown_email_returns_not_found(self, citizen_role):
        user = UserFactory(role=citizen_role)

        with pytest.raises(VerificationNotFoundException):
            EmailChangeService.verify_email_change(
                user=user,
                email='unknown@email.com',
                otp=TEST_OTP,
            )


@pytest.mark.django_db
class TestResendEmailChange:
    def test_resend_succeeds_after_cooldown(self, citizen_role, mocker):
        mocker.patch(
            'apps.accounts.services.verification_service.VerificationService._generate_otp',
            return_value='5678',
        )
        user = UserFactory(role=citizen_role)
        VerificationRequestFactory(
            email='new@email.com',
            purpose=EMAIL_CHANGE,
            last_sent_at=timezone.now() - timedelta(minutes=5),
            payload={'user_id': user.user_id, 'new_email': 'new@email.com'},
        )

        result = EmailChangeService.resend_email_change(user=user, email='new@email.com')

        assert result.is_success
        assert result.value.email == 'new@email.com'

    def test_resend_within_cooldown_returns_429(self, citizen_role):
        user = UserFactory(role=citizen_role)
        VerificationRequestFactory(
            email='new@email.com',
            purpose=EMAIL_CHANGE,
            last_sent_at=timezone.now(),
            payload={'user_id': user.user_id, 'new_email': 'new@email.com'},
        )

        result = EmailChangeService.resend_email_change(user=user, email='new@email.com')

        assert result.is_success is False
        assert result.error.error_code == 'OTP_RESEND_COOLDOWN_ACTIVE'

    def test_resend_unknown_email_returns_not_found(self, citizen_role):
        user = UserFactory(role=citizen_role)

        with pytest.raises(VerificationNotFoundException):
            EmailChangeService.resend_email_change(user=user, email='unknown@email.com')

    def test_resend_with_mismatched_user_returns_not_found(self, citizen_role):
        user = UserFactory(role=citizen_role)
        other = UserFactory(role=citizen_role)
        VerificationRequestFactory(
            email='new@email.com',
            purpose=EMAIL_CHANGE,
            payload={'user_id': user.user_id, 'new_email': 'new@email.com'},
        )

        with pytest.raises(VerificationNotFoundException):
            EmailChangeService.resend_email_change(user=other, email='new@email.com')

    def test_resend_limit_exceeded_deletes_and_returns_error(self, citizen_role):
        from django.conf import settings
        user = UserFactory(role=citizen_role)
        VerificationRequestFactory(
            email='new@email.com',
            purpose=EMAIL_CHANGE,
            resend_count=settings.VERIFICATION_REQUEST_CONFIG['MAX_RESENDS'],
            last_sent_at=timezone.now() - timedelta(minutes=5),
            payload={'user_id': user.user_id, 'new_email': 'new@email.com'},
        )

        result = EmailChangeService.resend_email_change(user=user, email='new@email.com')

        assert result.is_success is False
        assert result.error.error_code == 'OTP_RESEND_LIMIT_EXCEEDED'
        assert not VerificationRequest.objects.filter(
            email='new@email.com', purpose=EMAIL_CHANGE
        ).exists()
