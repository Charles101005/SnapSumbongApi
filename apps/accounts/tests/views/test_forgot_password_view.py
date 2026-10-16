from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import VerificationRequest
from apps.accounts.services import VerificationService
from apps.accounts.tests.factories import UserFactory, VerificationRequestFactory
from apps.accounts.tests.factories.verification_factory import TEST_OTP


FORGOT_URL = '/accounts/forgot-password/'
VERIFY_URL = '/accounts/forgot-password/verify/'
RESEND_URL = '/accounts/forgot-password/resend/'
RESET_URL = '/accounts/forgot-password/reset/'

FORGOT_PASSWORD = VerificationRequest.VerificationPurpose.FORGOT_PASSWORD


def _seed_otp_verification(email='reset@email.com', otp=TEST_OTP):
    return VerificationRequestFactory(
        email=email,
        purpose=FORGOT_PASSWORD,
        otp_hash=make_password(otp),
        payload={},
    )


def _seed_ready_verification(email='ready@email.com', *, expired=False):
    reset_token, reset_token_hash = VerificationService.generate_reset_token_and_hash()
    verification = VerificationRequestFactory(
        email=email,
        purpose=FORGOT_PASSWORD,
        otp_hash=None,
        payload={'reset_token_hash': reset_token_hash},
        expires_at=(
            timezone.now() - timedelta(minutes=1) if expired
            else timezone.now() + timedelta(minutes=10)
        ),
    )
    return verification, reset_token


@pytest.mark.django_db
class TestForgotPasswordView:
    def test_known_email_returns_generic_message_and_creates_verification(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        response = api_client.post(FORGOT_URL, {'email': user.email}, format='json')

        assert response.status_code == 200
        data = response.json()
        assert data['email'] == user.email
        assert 'Verification code has been sent' in data['detail']
        assert VerificationRequest.objects.filter(email=user.email, purpose=FORGOT_PASSWORD).exists()

    def test_unknown_email_returns_same_generic_message(self, api_client):
        response = api_client.post(FORGOT_URL, {'email': 'unknown@email.com'}, format='json')

        assert response.status_code == 200
        data = response.json()
        assert 'Verification code has been sent' in data['detail']
        assert data['email'] == 'unknown@email.com'

    def test_response_is_identical_for_known_and_unknown(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        known = api_client.post(FORGOT_URL, {'email': user.email}, format='json').json()
        unknown = api_client.post(FORGOT_URL, {'email': 'ghost@email.com'}, format='json').json()

        assert set(known.keys()) == set(unknown.keys())

    def test_invalid_email_returns_400(self, api_client):
        response = api_client.post(FORGOT_URL, {'email': 'not-an-email'}, format='json')

        assert response.status_code == 400


@pytest.mark.django_db
class TestVerifyForgotPasswordView:
    def test_correct_otp_returns_reset_token(self, api_client):
        verification = _seed_otp_verification()

        response = api_client.post(
            VERIFY_URL,
            {'email': verification.email, 'otp': TEST_OTP},
            format='json',
        )

        assert response.status_code == 200
        data = response.json()
        assert data['email'] == verification.email
        assert 'reset_token' in data

        verification.refresh_from_db()
        assert verification.otp_hash is None
        assert 'reset_token_hash' in verification.payload

    def test_wrong_otp_returns_400(self, api_client):
        verification = _seed_otp_verification()

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


@pytest.mark.django_db
class TestResendForgotPasswordVerificationCodeView:
    def test_resend_succeeds_after_cooldown(self, api_client, mocker):
        mocker.patch(
            'apps.accounts.services.verification_service.VerificationService._generate_otp',
            return_value='5678',
        )
        VerificationRequestFactory(
            email='reset@email.com',
            purpose=FORGOT_PASSWORD,
            last_sent_at=timezone.now() - timedelta(minutes=5),
        )

        response = api_client.post(RESEND_URL, {'email': 'reset@email.com'}, format='json')

        assert response.status_code == 200
        assert response.json()['email'] == 'reset@email.com'

    def test_resend_within_cooldown_returns_429(self, api_client):
        VerificationRequestFactory(
            email='reset@email.com',
            purpose=FORGOT_PASSWORD,
            last_sent_at=timezone.now(),
        )

        response = api_client.post(RESEND_URL, {'email': 'reset@email.com'}, format='json')

        assert response.status_code == 429
        assert response.json()['error_code'] == 'OTP_RESEND_COOLDOWN_ACTIVE'

    def test_resend_unknown_email_returns_404(self, api_client):
        response = api_client.post(RESEND_URL, {'email': 'unknown@email.com'}, format='json')

        assert response.status_code == 404


@pytest.mark.django_db
class TestResetPasswordView:
    def test_valid_token_resets_password(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        verification, reset_token = _seed_ready_verification(email=user.email)

        response = api_client.post(
            RESET_URL,
            {
                'email': user.email,
                'reset_token': reset_token,
                'new_password': 'NewPassword123!',
            },
            format='json',
        )

        assert response.status_code == 200
        assert response.json()['email'] == user.email

        user.refresh_from_db()
        assert user.check_password('NewPassword123!')
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_reset_revokes_existing_refresh_tokens(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        outstanding = RefreshToken.for_user(user)
        _, reset_token = _seed_ready_verification(email=user.email)

        api_client.post(
            RESET_URL,
            {
                'email': user.email,
                'reset_token': reset_token,
                'new_password': 'NewPassword123!',
            },
            format='json',
        )

        assert BlacklistedToken.objects.filter(token__token=str(outstanding)).exists()

    def test_wrong_reset_token_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        _seed_ready_verification(email=user.email)

        response = api_client.post(
            RESET_URL,
            {
                'email': user.email,
                'reset_token': 'wrong-token',
                'new_password': 'NewPassword123!',
            },
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'PASSWORD_RESET_INVALID'
        user.refresh_from_db()
        assert user.check_password('Password2005')

    def test_expired_reset_token_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        _, reset_token = _seed_ready_verification(email=user.email, expired=True)

        response = api_client.post(
            RESET_URL,
            {
                'email': user.email,
                'reset_token': reset_token,
                'new_password': 'NewPassword123!',
            },
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'PASSWORD_RESET_INVALID'

    def test_no_ready_request_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)

        response = api_client.post(
            RESET_URL,
            {
                'email': user.email,
                'reset_token': 'any-token',
                'new_password': 'NewPassword123!',
            },
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'PASSWORD_RESET_INVALID'

    def test_weak_new_password_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        _, reset_token = _seed_ready_verification(email=user.email)

        response = api_client.post(
            RESET_URL,
            {
                'email': user.email,
                'reset_token': reset_token,
                'new_password': 'password',
            },
            format='json',
        )

        assert response.status_code == 400
        assert 'new_password' in response.json()

