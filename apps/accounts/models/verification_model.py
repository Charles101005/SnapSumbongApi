from django.db import models
from django.utils import timezone
from django.conf import settings


class VerificationRequestQuerySet(models.QuerySet):
    def active(self):
        return self.filter(expires_at__gt = timezone.now())

    def expired(self):
        return self.filter(expires_at__lte = timezone.now())


class VerificationRequestManager(models.Manager.from_queryset(VerificationRequestQuerySet)):
    def get_or_none(self, email: str, purpose: str) -> 'VerificationRequest|None':
        return(
            self.get_queryset()
            .filter(email=email, purpose=purpose)
            .first()
        )

    def get_active_or_none(self, email: str, purpose: str) -> 'VerificationRequest|None':
        return(
            self.get_queryset()
            .active()
            .filter(email=email, purpose=purpose)
            .first()
        )

    def get_for_update_or_none(self, email: str, purpose: str) -> 'VerificationRequest|None':
        return(
            self.get_queryset()
            .select_for_update()
            .filter(email=email, purpose=purpose)
            .first()
        )

    def delete_abandoned(self) -> tuple[int, dict[str, int]]:
        threshold = settings.VERIFICATION_REQUEST_CONFIG['ABANDONED_THRESHOLD']
        cutoff = timezone.now() - threshold

        return self.filter(expires_at__lte=cutoff).delete()

    def get_password_reset_ready_or_none(self, email: str) -> 'VerificationRequest|None':
        return (
            self.get_queryset()
            .filter(
                email=email,
                purpose=VerificationRequest.VerificationPurpose.FORGOT_PASSWORD,
                otp_hash__isnull=True,
                payload__has_key="reset_token_hash"
            ).first()
        )


class VerificationRequest(models.Model):
    class VerificationPurpose(models.TextChoices):
        REGISTRATION = 'REGISTRATION'
        FORGOT_PASSWORD = 'FORGOT_PASSWORD'


    email = models.EmailField()
    purpose = models.CharField(choices=VerificationPurpose.choices, max_length=30)
    otp_hash = models.CharField(max_length=128, null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    attempts = models.PositiveSmallIntegerField(default=0)
    resend_count = models.PositiveSmallIntegerField(default=0)

    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


    objects = VerificationRequestManager()


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'purpose'],
                name='unique_verification_per_email_and_purpose'
            )
        ]