from datetime import timedelta

import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from apps.accounts.domain_errors.verification_error import InvalidVerificationOTPError
from apps.accounts.exceptions.verification_exception import VerificationNotFoundException
from apps.accounts.models import Users, VerificationRequest
from apps.accounts.services import RegisterService
from apps.accounts.tests.factories import VerificationRequestFactory
from apps.accounts.tests.factories.verification_factory import TEST_OTP


REGISTRATION = VerificationRequest.VerificationPurpose.REGISTRATION


def _seed_registration(email='pending@email.com', otp=TEST_OTP, middle_name='Santos'):
    return VerificationRequestFactory(
        email=email,
        purpose=REGISTRATION,
        otp_hash=make_password(otp),
        payload={
            'password_hash': make_password('Password2005'),
            'last_name': 'Dela Cruz',
            'first_name': 'Juan',
            'middle_name': middle_name,
        },
    )


@pytest.mark.django_db
class TestRegisterTempUser:
    def test_creates_registration_verification(self, mocker):
        mocker.patch(
            'apps.accounts.services.verification_service.VerificationService._generate_otp',
            return_value='1234',
        )

        result = RegisterService.register_temp_user(
            email='new@email.com',
            password='Password2005',
            last_name='Dela Cruz',
            first_name='Juan',
            middle_name='Santos',
        )

        assert result.is_success
        verification = result.value
        assert verification.email == 'new@email.com'
        assert verification.purpose == REGISTRATION
        assert verification.payload['last_name'] == 'Dela Cruz'
        assert verification.payload['first_name'] == 'Juan'
        assert verification.payload['middle_name'] == 'Santos'
        assert check_password('Password2005', verification.payload['password_hash'])

    def test_propagates_verification_in_progress_error(self, mocker):
        VerificationRequestFactory(
            email='pending@email.com',
            purpose=REGISTRATION,
            expires_at=timezone.now() + timedelta(minutes=1),
        )

        result = RegisterService.register_temp_user(
            email='pending@email.com',
            password='Password2005',
            last_name='Dela Cruz',
            first_name='Juan',
        )

        assert result.is_success is False
        assert result.error.error_code == 'VERIFICATION_IN_PROGRESS'


@pytest.mark.django_db
class TestVerifyTempUserAndCreateUser:
    def test_correct_otp_creates_citizen_and_deletes_verification(self, citizen_role):
        verification = _seed_registration()

        result = RegisterService.verify_temp_user_and_create_user(
            email=verification.email,
            otp=TEST_OTP,
        )

        assert result.is_success
        user = result.value
        assert user.email == verification.email
        assert user.first_name == 'Juan'
        assert user.last_name == 'Dela Cruz'
        assert user.middle_name == 'Santos'
        assert user.role_id == citizen_role.role_id
        assert user.check_password('Password2005')
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_wrong_otp_returns_error_and_keeps_verification(self):
        verification = _seed_registration()

        result = RegisterService.verify_temp_user_and_create_user(
            email=verification.email,
            otp='9999',
        )

        assert result.is_success is False
        assert result.error.error_code == InvalidVerificationOTPError.error_code
        assert VerificationRequest.objects.filter(pk=verification.pk).exists()
        assert not Users.objects.filter(email=verification.email).exists()

    def test_raises_when_no_verification_found(self):
        with pytest.raises(VerificationNotFoundException):
            RegisterService.verify_temp_user_and_create_user(
                email='none@email.com',
                otp=TEST_OTP,
            )

    def test_supports_missing_middle_name(self, citizen_role):
        verification = _seed_registration(middle_name=None)

        result = RegisterService.verify_temp_user_and_create_user(
            email=verification.email,
            otp=TEST_OTP,
        )

        assert result.is_success
        assert result.value.middle_name is None


@pytest.mark.django_db
class TestResendVerificationCode:
    def test_resends_registration_code(self, mocker):
        mocker.patch(
            'apps.accounts.services.verification_service.VerificationService._generate_otp',
            return_value='5678',
        )
        VerificationRequestFactory(
            email='resend@email.com',
            purpose=REGISTRATION,
            resend_count=0,
            last_sent_at=timezone.now() - timedelta(minutes=5),
        )

        result = RegisterService.resend_verification_code('resend@email.com')

        assert result.is_success
        assert result.value.purpose == REGISTRATION

    def test_raises_when_no_verification_found(self):
        with pytest.raises(VerificationNotFoundException):
            RegisterService.resend_verification_code('none@email.com')
