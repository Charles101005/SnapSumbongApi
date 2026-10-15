from django.db import models

from shared.utils import model_number_generator


class CitizenWarningManager(models.Manager):
    pass


class CitizenWarnings(models.Model):
    warning_id = models.BigAutoField(primary_key=True)

    # WARN-YYYYMMDD-6RandomBase36Chars
    warning_number = models.CharField(max_length=25, unique=True, db_index=True)

    user = models.ForeignKey(
        "apps_accounts.Users",
        on_delete=models.CASCADE,
        related_name="received_warnings",
    )

    warned_by = models.ForeignKey(
        "apps_accounts.Users",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_warnings",
    )

    reason = models.TextField()

    # Optional link to the INVALID report that triggered this warning.
    report = models.ForeignKey(
        "apps_reports.HazardReports",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_warnings",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    objects = CitizenWarningManager()

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.warning_number:
            self.warning_number = model_number_generator("WARN", suffix_length=6)

            while CitizenWarnings.objects.filter(warning_number=self.warning_number).exists():
                self.warning_number = model_number_generator("WARN", suffix_length=6)

        super().save(*args, **kwargs)
