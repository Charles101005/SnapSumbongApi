from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.accounts.models import VerificationRequest
from apps.accounts.services import EmailChangeService
from apps.accounts.tests.factories import RoleFactory, UserFactory, VerificationRequestFactory
from apps.accounts.tests.factories.verification_factory import TEST_OTP


EMAIL_CHANGE = VerificationRequest.VerificationPurpose.EMAIL_CHANGE

REQUEST_URL = '/accounts/profile/email-change/request/'
VERIFY_URL = '/accounts/profile/email-change/verify/'
RESEND_URL = '/accounts/profile/email-change/resend/'


@pytest.mark.django_db
class TestRequestEmailChangeView:
    def test_creates_verification_and_returns_200(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(REQUEST_URL, {'new_email': 'new@email.com'}, format='json')

        assert response.status_code == 200
        data = response.json()
        assert data['email'] == 'new@email.com'
        assert VerificationRequest.objects.filter(
            email='new@email.com', purpose=EMAIL_CHANGE
        ).exists()

    def test_same_email_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(REQUEST_URL, {'new_email': user.email}, format='json')

        assert response.status_code == 400
        assert 'new_email' in response.json()

    def test_same_email_case_insensitive_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role, email='user@email.com')
        api_client.force_authenticate(user=user)

        response = api_client.post(REQUEST_URL, {'new_email': 'USER@email.com'}, format='json')

        assert response.status_code == 400
        assert 'new_email' in response.json()

    def test_taken_email_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        UserFactory(role=citizen_role, email='taken@email.com')
        api_client.force_authenticate(user=user)

        response = api_client.post(REQUEST_URL, {'new_email': 'taken@email.com'}, format='json')

        assert response.status_code == 400
        assert 'new_email' in response.json()

    def test_pending_verification_returns_409(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        api_client.post(REQUEST_URL, {'new_email': 'new@email.com'}, format='json')
        response = api_client.post(REQUEST_URL, {'new_email': 'other@email.com'}, format='json')

        assert response.status_code == 409
        assert response.json()['error_code'] == 'VERIFICATION_IN_PROGRESS'

    def test_invalid_email_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(REQUEST_URL, {'new_email': 'not-an-email'}, format='json')

        assert response.status_code == 400

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post(REQUEST_URL, {'new_email': 'new@email.com'}, format='json')

        assert response.status_code == 401

    def test_permission_denied_without_update_own(self, api_client):
        no_perm_role = RoleFactory()
        user = UserFactory(role=no_perm_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(REQUEST_URL, {'new_email': 'new@email.com'}, format='json')

        assert response.status_code == 403


@pytest.mark.django_db
class TestVerifyEmailChangeView:
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

    def test_correct_otp_updates_email(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        verification = self._seed_verification(user, 'new@email.com')
        api_client.force_authenticate(user=user)

        response = api_client.post(
            VERIFY_URL,
            {'email': 'new@email.com', 'otp': TEST_OTP},
            format='json',
        )

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.email == 'new@email.com'
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_wrong_otp_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        verification = self._seed_verification(user, 'new@email.com')
        api_client.force_authenticate(user=user)

        response = api_client.post(
            VERIFY_URL,
            {'email': 'new@email.com', 'otp': '9999'},
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'INVALID_VERIFICATION_OTP'
        user.refresh_from_db()
        assert user.email != 'new@email.com'

    def test_mismatched_user_returns_400(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        other = UserFactory(role=citizen_role)
        verification = self._seed_verification(user, 'new@email.com')
        api_client.force_authenticate(user=other)

        response = api_client.post(
            VERIFY_URL,
            {'email': 'new@email.com', 'otp': TEST_OTP},
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'EMAIL_CHANGE_VERIFICATION_INVALID'
        assert not VerificationRequest.objects.filter(pk=verification.pk).exists()

    def test_unknown_email_returns_404(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            VERIFY_URL,
            {'email': 'unknown@email.com', 'otp': TEST_OTP},
            format='json',
        )

        assert response.status_code == 404
        assert response.json()['error_code'] == 'VERIFICATION_NOT_FOUND'

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post(
            VERIFY_URL,
            {'email': 'new@email.com', 'otp': TEST_OTP},
            format='json',
        )

        assert response.status_code == 401

    def test_permission_denied_without_update_own(self, api_client):
        no_perm_role = RoleFactory()
        user = UserFactory(role=no_perm_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            VERIFY_URL,
            {'email': 'new@email.com', 'otp': TEST_OTP},
            format='json',
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestResendEmailChangeView:
    def test_resend_succeeds_after_cooldown(self, api_client, citizen_role, mocker):
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
        api_client.force_authenticate(user=user)

        response = api_client.post(RESEND_URL, {'email': 'new@email.com'}, format='json')

        assert response.status_code == 200
        assert response.json()['email'] == 'new@email.com'

    def test_resend_within_cooldown_returns_429(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        VerificationRequestFactory(
            email='new@email.com',
            purpose=EMAIL_CHANGE,
            last_sent_at=timezone.now(),
            payload={'user_id': user.user_id, 'new_email': 'new@email.com'},
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(RESEND_URL, {'email': 'new@email.com'}, format='json')

        assert response.status_code == 429
        assert response.json()['error_code'] == 'OTP_RESEND_COOLDOWN_ACTIVE'

    def test_resend_unknown_email_returns_404(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(RESEND_URL, {'email': 'unknown@email.com'}, format='json')

        assert response.status_code == 404

    def test_resend_mismatched_user_returns_404(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        other = UserFactory(role=citizen_role)
        VerificationRequestFactory(
            email='new@email.com',
            purpose=EMAIL_CHANGE,
            payload={'user_id': user.user_id, 'new_email': 'new@email.com'},
        )
        api_client.force_authenticate(user=other)

        response = api_client.post(RESEND_URL, {'email': 'new@email.com'}, format='json')

        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post(RESEND_URL, {'email': 'new@email.com'}, format='json')

        assert response.status_code == 401

    def test_permission_denied_without_update_own(self, api_client):
        no_perm_role = RoleFactory()
        user = UserFactory(role=no_perm_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(RESEND_URL, {'email': 'new@email.com'}, format='json')

        assert response.status_code == 403
