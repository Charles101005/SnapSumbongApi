import string
import secrets

from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


def _generate_audit_log_number() -> str:
    # LOG-YYYYMMDD-6RandomBase36Chars

    PREFIX = "LOG"
    SUFFIX_LENGTH = 6
    SUFFIX_CHOICES = string.digits + string.ascii_uppercase

    date_str = timezone.now().strftime("%Y%m%d")
    suffix_str = ''.join(secrets.choice(SUFFIX_CHOICES) for _ in range(SUFFIX_LENGTH))

    return f"{PREFIX}-{date_str}-{suffix_str}"


class AuditLogs(models.Model):
    class ActionType(models.TextChoices):
        CREATE = "CREATE", "Creation of a new entity"
        UPDATE = "UPDATE", "Updated an existing entity"
        DEACTIVATE = "DEACTIVATE", "Deactivated an account"
        STATUS_CHANGE = "STATUS_CHANGE", "Status changed on a hazard report"
        SEVERITY_CHANGE = "SEVERITY_CHANGE", "Severity changed on a hazard report"

    class ModuleType(models.TextChoices):
        USER = "USER", "User"
        EMPLOYEE = "EMPLOYEE", "Employee"
        ROLE = "ROLE", "Role"
        REPORT = "REPORT", "Report"


    audit_log_id = models.BigAutoField(primary_key=True)

    # LOG-YYYYMMDD-6RandomBase36Chars
    audit_log_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        editable=False
    )

    user = models.ForeignKey(
        "apps_accounts.Users",
        on_delete=models.SET_NULL,
        null=True,
        related_name="actions_performed"
    )

    action = models.CharField(max_length=50, choices=ActionType.choices)
    module = models.CharField(max_length=50, choices=ModuleType.choices)

    description = models.CharField(max_length=255, null=True, blank=True)

    payload = models.JSONField(default=dict)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ["created_at"]

        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["action", "module"]),
        ]


    def save(self, *args, **kwargs):
        if not self.audit_log_number:
            self.audit_log_number = _generate_audit_log_number()

            while AuditLogs.objects.filter(audit_log_number=self.audit_log_number).exists():
                self.audit_log_number = _generate_audit_log_number()

        super().save(*args, **kwargs)
