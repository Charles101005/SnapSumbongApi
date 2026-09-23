import string
import secrets

from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation

from .hazard_category_model import HazardCategories


def _generate_report_number() -> str:
    # REPT-YYYYMMDD-6RandomBase36Chars

    PREFIX = "REPT"
    SUFFIX_LENGTH = 6
    SUFFIX_CHOICES = string.digits + string.ascii_uppercase

    date_str = timezone.now().strftime("%Y%m%d")
    suffix_str = ''.join(secrets.choice(SUFFIX_CHOICES) for _ in range(SUFFIX_LENGTH))

    return f"{PREFIX}-{date_str}-{suffix_str}"


class HazardReportManager(models.Manager):
    pass


class HazardReports(models.Model):
    class Severity(models.TextChoices):
        P1 = 'P1', 'P1 - Critical (Immediate Danger)'
        P2 = 'P2', 'P2 - High (Significant Hazard)'
        P3 = 'P3', 'P3 - Medium (Standard Hazard)'
        P4 = 'P4', 'P4 - Low (Minor Concern)'
        P5 = 'P5', 'P5 - Very Low (Cosmetic/Informational)'


    class Status(models.TextChoices):
        # Phase 1: Intake and Assignment(more for the system)
        NEW = 'NEW', 'New' #'Newly Submitted'
        ASSIGNED = 'ASSIGNED', 'Assigned' #'Assigned to Officer'

        # Phase 2: Report Verification
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review' #'Being worked on/Report Verification'
        ON_HOLD = 'ON_HOLD', 'On-Hold' #'Out of Jurisdiction/Need External Department' #

        # Phase 3: Action
        DISPATCHED = 'DISPATCHED', 'Dispatched' #'Dispatched Engineers'

        # Phase 4: Resolution and Closure
        RESOLVED = 'RESOLVED', 'Resolved' #'Issue is solved but needs user verification'
        CLOSED = 'CLOSED', 'Closed' #'Automatically or manually closed' #

        @property
        def phase(self) -> int:
            phase_map = {
                self.NEW: 1,
                self.ASSIGNED: 1,

                self.UNDER_REVIEW: 2,
                self.ON_HOLD: 2,

                self.DISPATCHED: 3,

                self.RESOLVED: 4,
                self.CLOSED: 4,
            }
            return phase_map[self]

        @classmethod
        def get_main_statuses(cls) -> list:
            return [
                cls.ASSIGNED,
                cls.UNDER_REVIEW,
                cls.DISPATCHED,
                cls.RESOLVED,
            ]

        @classmethod
        def get_mandatory_remarks_statuses(cls) -> list:
            return [
                cls.ON_HOLD,
                cls.CLOSED,
            ]

        def get_next_expected_statuses(self) -> list:
            current_phase = self.phase
            main_statuses = self.get_main_statuses()

            return [
                status.label
                for status in main_statuses
                if status.phase > current_phase
            ]


    report_id = models.BigAutoField(primary_key=True)

    # REPT-YYYYMMDD-6RandomBase36Chars
    report_number = models.CharField(max_length=20, unique=True, db_index=True)

    reported_by = models.ForeignKey(
        "apps_accounts.Users",
        on_delete=models.SET_NULL,
        null=True,
        related_name="hazard_reports",
    )

    assigned_to = models.ForeignKey(
        "apps_accounts.Users",
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_hazard_reports",
    )

    category = models.ForeignKey(HazardCategories, on_delete=models.PROTECT, related_name="hazard_reports")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    severity = models.CharField(max_length=2, choices=Severity.choices, null=True, blank=True, db_index=True)

    latitude = models.DecimalField(max_digits=8, decimal_places=6) # -90 to 90
    longitude = models.DecimalField(max_digits=9, decimal_places=6) # -180 to 180
    address = models.CharField(max_length=255)

    description = models.TextField()
    is_anonymous = models.BooleanField(default=False)

    remarks = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True)

    audit_logs = GenericRelation(
        "apps_audits.AuditLogs",
        object_id_field="object_id",
        content_type_field="content_type"
    )


    objects = HazardReportManager()

    def save(self, *args, **kwargs):
        if not self.report_number:
            self.report_number = _generate_report_number()

            while HazardReports.objects.filter(report_number=self.report_number).exists():
                self.report_number = _generate_report_number()

        super().save(*args, **kwargs)
