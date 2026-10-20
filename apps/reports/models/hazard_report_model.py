from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation

from .hazard_category_model import HazardCategories
from shared.utils import model_number_generator


class HazardReportManager(models.Manager):
    pass


# UI transition matrix. Closed is a destination the process arrives at, not
# a shortcut: verification (Under Review) must come first, early-phase
# reports close only via On-Hold (referred out), and completed works close
# only via Resolved. Assigned leads directly into Under Review — no other
# next stage — and Invalid is only a triage verdict from Under Review
# onward (fake/troll reports are flagged after verification has begun).
# This map feeds HazardReports.Status.get_next_expected_statuses, which
# the staff modal uses to restrict its status dropdown; ReportService also
# enforces the Assigned rule server-side (every other row stays UI-only).
STATUS_ALLOWED_TRANSITIONS = {
    'NEW': ('UNDER_REVIEW', 'INVALID'),
    'ASSIGNED': ('UNDER_REVIEW',),
    'UNDER_REVIEW': ('ON_HOLD', 'DISPATCHED', 'INVALID'),
    'ON_HOLD': ('UNDER_REVIEW', 'DISPATCHED', 'CLOSED', 'INVALID'),
    'DISPATCHED': ('ONGOING', 'RESOLVED', 'ON_HOLD', 'INVALID'),
    'ONGOING': ('RESOLVED', 'ON_HOLD'),
    'RESOLVED': ('CLOSED',),
    'CLOSED': (),
    'INVALID': (),
}


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
        ONGOING = 'ONGOING', 'Ongoing' #'Crew on Site — Works in Progress'

        # Phase 4: Resolution and Closure
        RESOLVED = 'RESOLVED', 'Resolved' #'Issue is solved but needs user verification'
        CLOSED = 'CLOSED', 'Closed' #'Closed by reporter confirmation, or force-closed by staff (e.g. out of DO 47 jurisdiction)' #
        INVALID = 'INVALID', 'Invalid' #'Closed as false/unverifiable — moderation action on suspected fake or troll reports'

        @property
        def phase(self) -> int:
            phase_map = {
                self.NEW: 1,
                self.ASSIGNED: 1,

                self.UNDER_REVIEW: 2,
                self.ON_HOLD: 2,

                self.DISPATCHED: 3,
                self.ONGOING: 3,

                self.RESOLVED: 4,
                self.CLOSED: 4,
                self.INVALID: 4,
            }
            return phase_map[self]

        @classmethod
        def get_mandatory_remarks_statuses(cls) -> list:
            return [
                cls.ON_HOLD,
                cls.CLOSED,
                cls.INVALID,
            ]

        def get_next_expected_statuses(self) -> list:
            return [
                type(self)(value).label
                for value in STATUS_ALLOWED_TRANSITIONS.get(self.value, ())
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

    # DO 47 s.2024 §2: the staff member who validated the completed
    # rectification works. The resolving officer declares this name manually
    # (typed into the resolve form); it may be any technical personnel,
    # including the assigned handler.
    validated_by_name = models.CharField(max_length=150, null=True, blank=True)

    # The account that performed the resolve action in the system (audit).
    validated_by = models.ForeignKey(
        "apps_accounts.Users",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validated_hazard_reports",
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

    # DO 47 s.2024 §4.1: due date = date noted + category response time.
    # Null only for reports created before SLA tracking existed.
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True)

    # Set only when the reporter (citizen) confirms the completed works and
    # the report moves RESOLVED -> CLOSED. A CLOSED report with a null
    # confirmed_at was force-closed by staff (e.g. out of DO 47 jurisdiction).
    confirmed_at = models.DateTimeField(null=True, blank=True)

    audit_logs = GenericRelation(
        "apps_audits.AuditLogs",
        object_id_field="object_id",
        content_type_field="content_type"
    )


    objects = HazardReportManager()

    @property
    def is_overdue(self) -> bool:
        # Phase-4 statuses (RESOLVED, CLOSED) are never overdue.
        if not self.due_at or HazardReports.Status(self.status).phase == 4:
            return False

        return timezone.now() > self.due_at

    def save(self, *args, **kwargs):
        if not self.report_number:
            self.report_number = model_number_generator("REPT")

            while HazardReports.objects.filter(report_number=self.report_number).exists():
                self.report_number = model_number_generator("REPT")

        super().save(*args, **kwargs)
