from django.db import models
from django.utils import timezone


class VerificationRequestQuerySet(models.QuerySet):
    def active(self):
        return self.filter(expires_at__gt = timezone.now())

    def expired(self):
        return self.filter(expires_at__lte = timezone.now())


class VerificationRequestManager(models.Manager.from_queryset(VerificationRequestQuerySet)):
    def get_active_or_none(self, email: str, purpose: str) -> 'VerificationRequest|None':
        return(
            self.get_queryset()
            .active()
            .filter(email=email, purpose=purpose)
            .first()
        )

    def delete_expired(self) -> 'VerificationRequest':
        return self.get_queryset().expired().delete()


class VerificationRequest(models.Model):
    class VerificationPurpose(models.TextChoices):
        REGISTRATION = 'REGISTRATION'
        RESET_PASSWORD = 'RESET_PASSWORD'


    email = models.EmailField()
    purpose = models.CharField(choices=VerificationPurpose.choices, max_length=30)
    otp_hash = models.CharField(max_length=128)
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