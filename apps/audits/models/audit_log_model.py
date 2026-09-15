from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


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
