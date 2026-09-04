from django.db import models

from .hazard_category_model import HazardCategories


class HazardReports(models.Model):
    class Severity(models.TextChoices):
        P1 = 'P1', 'P1 - Critical (Immediate Danger)'
        P2 = 'P2', 'P2 - High (Significant Hazard)'
        P3 = 'P3', 'P3 - Medium (Standard Hazard)'
        P4 = 'P4', 'P4 - Low (Minor Concern)'
        P5 = 'P5', 'P5 - Very Low (Cosmetic/Informational)'


    class Status(models.TextChoices):
        # Phase 1: Intake and Assignment
        NEW = 'NEW', 'New - Newly Submitted'
        OPEN = 'OPEN', 'Open - Assigned to Officer'

        # Phase 2: Report Verification
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress - Being worked on/Report Verification'
        PENDING = 'PENDING', 'Pending - Invalid/Insufficient Information'
        ON_HOLD = 'ON_HOLD', 'On Hold - Out of Jurisdiction/Need External Department'

        # Phase 3: Action
        UNDER_REPAIR = 'UNDER_REPAIR', 'Under Repair - Dispatched Engineers'

        # Phase 4: Resolution and Closure
        RESOLVED = 'RESOLVED', 'Resolved - Issue is solved but needs user verification'
        CLOSED = 'CLOSED', 'Closed - Automatically or manually closed'

        @property
        def phase(self) -> int:
            phase_map = {
                self.NEW: 1,
                self.OPEN: 1,

                self.IN_PROGRESS: 2,
                self.PENDING: 2,
                self.ON_HOLD: 2,

                self.UNDER_REPAIR: 3,

                self.RESOLVED: 4,
                self.CLOSED: 4,
            }
            return phase_map[self]


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

    categories = models.ManyToManyField(HazardCategories, related_name="hazard_reports")
    severity = models.CharField(max_length=2, choices=Severity.choices, null=True, blank=True, db_index=True)

    latitude = models.DecimalField(max_digits=8, decimal_places=6) # -90 to 90
    longitude = models.DecimalField(max_digits=9, decimal_places=6) # -180 to 180
    address = models.CharField(max_length=255)

    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    is_anonymous = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True)
