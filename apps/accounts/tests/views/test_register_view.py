from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.accounts.models import Users, VerificationRequest
from apps.accounts.tests.factories import UserFactory, VerificationRequestFactory
from apps.accounts.tests.factories.verification_factory import TEST_OTP


REGISTER_URL = '/accounts/register/'
VERIFY_URL = '/accounts/register/verify/'
RESEND_URL = '/accounts/register/resend/'

REGISTRATION = VerificationRequest.VerificationPurpose.REGISTRATION


def _valid_payload(**overrides):
    payload = {
        'email': 'newuser@email.com',
        'password': 'Password2005!',
        'last_name': 'Dela Cruz',
        'first_name': 'Juan',
        'middle_name': 'Santos',
    }
    payload.update(overrides)
    return payload


def _seed_verification(email='pending@email.com', otp=TEST_OTP):
    return VerificationRequestFactory(
        email=email,
        purpose=REGISTRATION,
        otp_hash=make_password(otp),
        payload={
            'password_hash': make_password('Password2005'),
            'last_name': 'Dela Cruz',
            'first_name': 'Juan',
            'middle_name': 'Santos',
        },
    )


@pytest.mark.django_db
class TestRegistrationView:
    def test_successful_registration_creates_verification(self, api_client, mocker):
        mocker.patch(
            'apps.accounts.services.verification_service.VerificationService._generate_otp',
            return_value='1234',
        )

        response = api_client.post(REGISTER_URL, _valid_payload(), format='json')

        assert response.status_code == 201
        data = response.json()
        assert data['email'] == 'newuser@email.com'
        assert 'expires_at' in data
        assert VerificationRequest.objects.filter(
            email='newuser@email.com',
            purpose=REGISTRATION,
        ).exists()

    def test_duplicate_email_returns_400(self, api_client):
        UserFactory(email='newuser@email.com')

        response = api_client.post(REGISTER_URL, _valid_payload(), format='json')

        assert response.status_code == 400
        assert 'email' in response.json()

    def test_weak_password_returns_400(self, api_client):
        response = api_client.post(
            REGISTER_URL,
            _valid_payload(password='password'),
            format='json',
        )

        assert response.status_code == 400
        assert 'password' in response.json()

    def test_invalid_email_returns_400(self, api_client):
        response = api_client.post(
            REGISTER_URL,
            _valid_payload(email='not-an-email'),
            format='json',
        )

        assert response.status_code == 400
        assert 'email' in response.json()

    def test_missing_fields_returns_400(self, api_client):
        response = api_client.post(REGISTER_URL, {'email': 'x@email.com'}, format='json')

        assert response.status_code == 400

    def test_conflicting_active_verification_returns_409(self, api_client):
        VerificationRequestFactory(
            email='newuser@email.com',
            purpose=REGISTRATION,
            expires_at=timezone.now() + timedelta(minutes=1),
        )

        response = api_client.post(REGISTER_URL, _valid_payload(), format='json')

        assert response.status_code == 409
        assert response.json()['error_code'] == 'VERIFICATION_IN_PROGRESS'


@pytest.mark.django_db
class TestVerifyRegistrationView:
    def test_correct_otp_creates_user_and_returns_201(self, api_client, citizen_role):
        verification = _seed_verification()

        response = api_client.post(
            VERIFY_URL,
            {'email': verification.email, 'otp': TEST_OTP},
            format='json',
        )

        assert response.status_code == 201
        assert response.json()['email'] == verification.email
        user = Users.objects.get(email=verification.email)
        assert user.role_id == citizen_role.role_id
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_wrong_otp_returns_400(self, api_client):
        verification = _seed_verification()

        response = api_client.post(
            VERIFY_URL,
            {'email': verification.email, 'otp': '9999'},
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'INVALID_VERIFICATION_OTP'

    def test_unknown_email_returns_404(self, api_client):
        response = api_client.post(
            VERIFY_URL,
            {'email': 'unknown@email.com', 'otp': TEST_OTP},
            format='json',
        )

        assert response.status_code == 404
        assert response.json()['error_code'] == 'VERIFICATION_NOT_FOUND'

    def test_invalid_otp_length_returns_400(self, api_client):
        verification = _seed_verification()

        response = api_client.post(
            VERIFY_URL,
            {'email': verification.email, 'otp': '12'},
            format='json',
        )

        assert response.status_code == 400
        assert 'otp' in response.json()


@pytest.mark.django_db
class TestResendRegisterVerificationCodeView:
    def test_resend_succeeds_after_cooldown(self, api_client, mocker):
        mocker.patch(
            'apps.accounts.services.verification_service.VerificationService._generate_otp',
            return_value='5678',
        )
        VerificationRequestFactory(
            email='pending@email.com',
            purpose=REGISTRATION,
            last_sent_at=timezone.now() - timedelta(minutes=5),
        )

        response = api_client.post(RESEND_URL, {'email': 'pending@email.com'}, format='json')

        assert response.status_code == 200
        assert response.json()['email'] == 'pending@email.com'

    def test_resend_within_cooldown_returns_429(self, api_client):
        VerificationRequestFactory(
            email='pending@email.com',
            purpose=REGISTRATION,
            last_sent_at=timezone.now(),
        )

        response = api_client.post(RESEND_URL, {'email': 'pending@email.com'}, format='json')

        assert response.status_code == 429
        assert response.json()['error_code'] == 'OTP_RESEND_COOLDOWN_ACTIVE'

    def test_resend_unknown_email_returns_404(self, api_client):
        response = api_client.post(RESEND_URL, {'email': 'unknown@email.com'}, format='json')

        assert response.status_code == 404
        assert response.json()['error_code'] == 'VERIFICATION_NOT_FOUND'

    def test_invalid_email_returns_400(self, api_client):
        response = api_client.post(RESEND_URL, {'email': 'not-an-email'}, format='json')

        assert response.status_code == 400
