from django.utils import timezone
from rest_framework import serializers

from apps.accounts.services.verification_service import VerificationService


class VerificationSessionCreationResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    expires_at = serializers.DateTimeField()
    # Seconds until another resend is allowed — lets the frontend start a
    # countdown the moment a code is requested (no extra round-trip).
    retry_after_seconds = serializers.SerializerMethodField()

    def get_retry_after_seconds(self, obj) -> int:
        return VerificationService.retry_after_seconds(obj.last_sent_at, timezone.now())
