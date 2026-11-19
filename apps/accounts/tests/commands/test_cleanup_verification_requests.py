from datetime import timedelta
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import VerificationRequest
from apps.accounts.tests.factories import VerificationRequestFactory


def _abandoned():
    threshold = settings.VERIFICATION_REQUEST_CONFIG["ABANDONED_THRESHOLD"]
    return VerificationRequestFactory(
        expires_at=timezone.now() - threshold - timedelta(minutes=1)
    )


@pytest.mark.django_db
class TestCleanupVerificationRequests:
    def test_deletes_only_requests_past_the_abandoned_threshold(self):
        abandoned = _abandoned()
        recently_expired = VerificationRequestFactory(
            expires_at=timezone.now() - timedelta(seconds=30)
        )
        active = VerificationRequestFactory()
        stdout = StringIO()

        call_command("cleanup_verification_requests", stdout=stdout)

        assert not VerificationRequest.objects.filter(pk=abandoned.pk).exists()
        assert VerificationRequest.objects.filter(pk=recently_expired.pk).exists()
        assert VerificationRequest.objects.filter(pk=active.pk).exists()
        assert "Deleted 1 abandoned verification request(s)" in stdout.getvalue()

    def test_dry_run_keeps_rows_and_reports_count(self):
        _abandoned()
        stdout = StringIO()

        call_command("cleanup_verification_requests", "--dry-run", stdout=stdout)

        assert VerificationRequest.objects.count() == 1
        assert "would be deleted" in stdout.getvalue()
