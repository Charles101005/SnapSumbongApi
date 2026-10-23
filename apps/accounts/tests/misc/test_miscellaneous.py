import types

import pytest
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from apps.accounts.domain_errors.user_error import UserNotFoundError
from apps.accounts.middleware import UpdateLastActiveMiddleware
from apps.accounts.models import VerificationRequest
from apps.accounts.serializers.request.profile_serializer import RequestEmailChangeRequestSerializer
from apps.accounts.services import RegisterService, VerificationService
from apps.accounts.tests.factories import UserFactory, VerificationRequestFactory
from apps.accounts.tests.factories.verification_factory import TEST_OTP
from shared.results import DomainResult


LOGIN_URL = '/accounts/auth/login/'


@pytest.mark.django_db
class TestUpdateLastActiveMiddleware:
    def test_stale_last_active_is_updated(self, citizen_role):
        user = UserFactory(role=citizen_role)  # last_active defaults to None

        request = types.SimpleNamespace(user=user)
        UpdateLastActiveMiddleware(get_response=lambda req: None)(request)

        user.refresh_from_db()
        assert user.last_active is not None

    def test_recent_last_active_is_not_updated(self, citizen_role):
        user = UserFactory(role=citizen_role)
        user.last_active = timezone.now()
        user.save()
        user.refresh_from_db()
        before = user.last_active

        request = types.SimpleNamespace(user=user)
        UpdateLastActiveMiddleware(get_response=lambda req: None)(request)

        user.refresh_from_db()
        assert user.last_active == before


@pytest.mark.django_db
class TestUserModelStr:
    def test_str_returns_email(self, citizen_role):
        user = UserFactory(role=citizen_role)

        assert str(user) == user.email


@pytest.mark.django_db
class TestSendOtpDispatch:
    def test_registration_otp_is_emailed_on_commit(self, django_capture_on_commit_callbacks, mocker):
        send_otp = mocker.patch('external.email.EmailService.send_registration_otp', return_value=True)

        with django_capture_on_commit_callbacks(execute=True):
            VerificationService.create(
                email='send-otp@email.com',
                purpose=VerificationRequest.VerificationPurpose.REGISTRATION,
                payload={'first_name': 'Juan'},
            )

        send_otp.assert_called_once_with(
            to_email='send-otp@email.com',
            to_first_name='Juan',
            otp_code=mocker.ANY,
            expiry_minutes=settings.VERIFICATION_REQUEST_CONFIG.get(
                "VERIFICATION_REQUEST_LIFETIME"
            ).total_seconds() // 60,
        )


@pytest.mark.django_db
class TestLoginViewNonOkPath:
    def test_non_200_login_response_is_returned_without_cookie(self, api_client, mocker):
        non_ok = Response({'detail': 'failed'}, status=status.HTTP_400_BAD_REQUEST)
        mocker.patch(
            'rest_framework_simplejwt.views.TokenObtainPairView.post',
            return_value=non_ok,
        )

        response = api_client.post(LOGIN_URL, {'email': 'x@email.com', 'password': 'bad'})

        assert response.status_code == 400
        assert 'refresh' not in response.cookies


@pytest.mark.django_db
class TestVerifyTempUserErrorPropagation:
    def test_create_verified_citizen_error_is_propagated(self, mocker):
        mocker.patch(
            'apps.accounts.services.register_service.UserService.create_verified_citizen',
            return_value=DomainResult.error(UserNotFoundError),
        )
        verification = VerificationRequestFactory(
            email='reg-error@email.com',
            purpose=VerificationRequest.VerificationPurpose.REGISTRATION,
            otp_hash=make_password(TEST_OTP),
            payload={
                'password_hash': make_password('Password2005'),
                'last_name': 'Dela Cruz',
                'first_name': 'Juan',
                'middle_name': 'Santos',
            },
        )

        result = RegisterService.verify_temp_user_and_create_user(
            email=verification.email,
            otp=TEST_OTP,
        )

        assert result.is_success is False
        assert result.error is UserNotFoundError
        assert VerificationRequest.objects.filter(pk=verification.pk).exists()


class TestRequestEmailChangeSerializerNoUserContext:
    def test_valid_email_passes_without_user_in_context(self):
        serializer = RequestEmailChangeRequestSerializer(
            data={'new_email': 'new@email.com'},
        )

        assert serializer.is_valid() is True
        assert serializer.validated_data['new_email'] == 'new@email.com'

    def test_invalid_email_still_rejected_without_user_in_context(self):
        serializer = RequestEmailChangeRequestSerializer(
            data={'new_email': 'not-an-email'},
        )

        assert serializer.is_valid() is False
        assert 'new_email' in serializer.errors
