from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import VerificationRequest
from apps.accounts.tests.factories import VerificationRequestFactory


REGISTRATION = VerificationRequest.VerificationPurpose.REGISTRATION
FORGOT_PASSWORD = VerificationRequest.VerificationPurpose.FORGOT_PASSWORD


@pytest.mark.django_db
class TestVerificationRequestQuerySet:
    def test_active_filters_unexpired(self):
        unexpired = VerificationRequestFactory(expires_at=timezone.now() + timedelta(minutes=1))
        VerificationRequestFactory(expires_at=timezone.now() - timedelta(minutes=1))

        active = list(VerificationRequest.objects.active())

        assert active == [unexpired]

    def test_expired_filters_expired(self):
        VerificationRequestFactory(expires_at=timezone.now() + timedelta(minutes=1))
        expired = VerificationRequestFactory(expires_at=timezone.now() - timedelta(minutes=1))

        expired_rows = list(VerificationRequest.objects.expired())

        assert expired_rows == [expired]


@pytest.mark.django_db
class TestVerificationRequestManager:
    def test_get_or_none_when_exists(self):
        verification = VerificationRequestFactory(email='find@email.com', purpose=REGISTRATION)

        found = VerificationRequest.objects.get_or_none(email='find@email.com', purpose=REGISTRATION)

        assert found == verification

    def test_get_or_none_when_missing(self):
        assert VerificationRequest.objects.get_or_none(email='missing@email.com', purpose=REGISTRATION) is None

    def test_get_or_none_is_scoped_by_purpose(self):
        verification = VerificationRequestFactory(email='scoped@email.com', purpose=REGISTRATION)

        found = VerificationRequest.objects.get_or_none(email='scoped@email.com', purpose=FORGOT_PASSWORD)

        assert found is None
        assert verification.purpose == REGISTRATION

    def test_get_active_or_none_when_unexpired(self):
        verification = VerificationRequestFactory(expires_at=timezone.now() + timedelta(minutes=1))

        found = VerificationRequest.objects.get_active_or_none(
            email=verification.email,
            purpose=verification.purpose,
        )

        assert found == verification

    def test_get_active_or_none_when_expired(self):
        verification = VerificationRequestFactory(expires_at=timezone.now() - timedelta(minutes=1))

        found = VerificationRequest.objects.get_active_or_none(
            email=verification.email,
            purpose=verification.purpose,
        )

        assert found is None

    def test_get_for_update_or_none_returns_row(self):
        verification = VerificationRequestFactory()

        found = VerificationRequest.objects.get_for_update_or_none(
            email=verification.email,
            purpose=verification.purpose,
        )

        assert found == verification

    def test_get_for_update_or_none_when_missing(self):
        assert VerificationRequest.objects.get_for_update_or_none(
            email='missing@email.com',
            purpose=REGISTRATION,
        ) is None

    def test_delete_abandoned_removes_only_past_threshold(self):
        threshold = settings.VERIFICATION_REQUEST_CONFIG['ABANDONED_THRESHOLD']

        abandoned = VerificationRequestFactory(expires_at=timezone.now() - threshold - timedelta(minutes=1))
        recently_expired = VerificationRequestFactory(expires_at=timezone.now() - timedelta(seconds=30))

        deleted_count, _ = VerificationRequest.objects.delete_abandoned()

        assert deleted_count == 1
        assert not VerificationRequest.objects.filter(pk=abandoned.pk).exists()
        assert VerificationRequest.objects.filter(pk=recently_expired.pk).exists()

    def test_get_password_reset_ready_or_none_when_ready(self):
        verification = VerificationRequestFactory(
            purpose=FORGOT_PASSWORD,
            otp_hash=None,
            payload={'reset_token_hash': 'abc123'},
        )

        found = VerificationRequest.objects.get_password_reset_ready_or_none(email=verification.email)

        assert found == verification

    def test_get_password_reset_ready_or_none_requires_otp_cleared(self):
        verification = VerificationRequestFactory(
            purpose=FORGOT_PASSWORD,
            payload={'reset_token_hash': 'abc123'},
        )

        found = VerificationRequest.objects.get_password_reset_ready_or_none(email=verification.email)

        assert found is None

    def test_get_password_reset_ready_or_none_requires_reset_token_hash(self):
        verification = VerificationRequestFactory(
            purpose=FORGOT_PASSWORD,
            otp_hash=None,
            payload={},
        )

        found = VerificationRequest.objects.get_password_reset_ready_or_none(email=verification.email)

        assert found is None

    def test_get_password_reset_ready_or_none_scopes_by_purpose(self):
        VerificationRequestFactory(
            purpose=REGISTRATION,
            otp_hash=None,
            payload={'reset_token_hash': 'abc123'},
        )

        found = VerificationRequest.objects.get_password_reset_ready_or_none(email='registration@email.com')

        assert found is None

