from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation

from .hazard_category_model import HazardCategories
from shared.utils import model_number_generator


class HazardReportManager(models.Manager):
    pass


# UI transition matrix. Closed is a destination the process arrives at, not
# a shortcut: a report must be handled (In Progress) before it can resolve or
# be referred out, early-phase reports close only via On-Hold (referred out),
# and completed works close only via Resolved. Assigned leads directly into
# In Progress — no other next stage — and Invalid is only a triage verdict
# once handling has begun (fake/troll reports are flagged after assessment).
# The service allows one extra path: Assigned -> Invalid when a pending AI
# screening flag is confirmed as fake in the same save.
#
# Validation, dispatch, and field work are ACTIVITIES inside In Progress, not
# separate ticket statuses. They are recorded through the activity log and
# shown as sub-events on the report timeline.
#
# This map feeds HazardReports.Status.get_next_expected_statuses, which
# the staff modal uses to restrict its status dropdown; ReportService also
# enforces the Assigned rule server-side (every other row stays UI-only).
STATUS_ALLOWED_TRANSITIONS = {
    'NEW': ('ASSIGNED', 'INVALID'),
    'ASSIGNED': ('IN_PROGRESS',),
    'IN_PROGRESS': ('ON_HOLD', 'RESOLVED', 'INVALID'),
    'ON_HOLD': ('IN_PROGRESS', 'CLOSED', 'INVALID'),
    'RESOLVED': ('CLOSED',),
    'CLOSED': (),
    'INVALID': (),
}

# Historical audit rows still carry the labels/codes of the retired statuses.
# They are rendered as activities instead of being rewritten, so the audit
# trail keeps its original wording while the UI speaks the 7-status language.
LEGACY_STATUS_TO_CODE = {
    'UNDER_REVIEW': 'IN_PROGRESS',
    'DISPATCHED': 'IN_PROGRESS',
    'ONGOING': 'IN_PROGRESS',
}

LEGACY_STATUS_ACTIVITY_LABELS = {
    'UNDER_REVIEW': 'Report validated',
    'DISPATCHED': 'Forwarded to field personnel',
    'ONGOING': 'Corrective work started',
}


class HazardReports(models.Model):
    class Severity(models.TextChoices):
        P1 = 'P1', 'P1 - Critical (Immediate Danger)'
        P2 = 'P2', 'P2 - High (Significant Hazard)'
        P3 = 'P3', 'P3 - Medium (Standard Hazard)'
        P4 = 'P4', 'P4 - Low (Minor Concern)'
        P5 = 'P5', 'P5 - Very Low (Cosmetic/Informational)'


    class Status(models.TextChoices):
        # Phase 1: Intake and Assignment (system-managed)
        NEW = 'NEW', 'New'
        ASSIGNED = 'ASSIGNED', 'Assigned'

        # Phase 2: Handling — validation, assessment, coordination, and
        # corrective actions all happen while the report is In Progress.
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        ON_HOLD = 'ON_HOLD', 'On-Hold'

        # Phase 4: Resolution and Closure
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'
        INVALID = 'INVALID', 'Invalid'

        @property
        def phase(self) -> int:
            phase_map = {
                self.NEW: 1,
                self.ASSIGNED: 1,

                self.IN_PROGRESS: 2,
                self.ON_HOLD: 2,

                self.RESOLVED: 4,
                self.CLOSED: 4,
                self.INVALID: 4,
            }
            return phase_map[self]

        @property
        def is_terminal(self) -> bool:
            # Resolved still needs citizen confirmation (or a staff force-close),
            # so only Closed and Invalid are truly terminal.
            return self in (self.CLOSED, self.INVALID)

        @property
        def description(self) -> str:
            description_map = {
                self.NEW: (
                    "The report has been successfully submitted by the citizen "
                    "and is awaiting initial assessment and assignment by the LGU."
                ),
                self.ASSIGNED: (
                    "The report has been assigned to a designated LGU officer who "
                    "is responsible for handling and monitoring the reported hazard."
                ),
                self.IN_PROGRESS: (
                    "The LGU officer is actively handling the report, including "
                    "validating the submitted information, assessing the reported "
                    "hazard, coordinating with the appropriate department or field "
                    "personnel, and carrying out the necessary corrective actions."
                ),
                self.ON_HOLD: (
                    "The report is temporarily paused pending additional "
                    "information, further verification, resource availability, or "
                    "referral to the appropriate agency when the reported issue "
                    "falls outside the LGU's jurisdiction."
                ),
                self.RESOLVED: (
                    "The reported hazard has been addressed and the necessary "
                    "corrective actions have been completed. The report is awaiting "
                    "final confirmation and closure."
                ),
                self.CLOSED: (
                    "The report has been verified as completed and officially "
                    "closed. No further action is required."
                ),
                self.INVALID: (
                    "The report has been determined to be false, misleading, spam, "
                    "or otherwise invalid after assessment. No further action will "
                    "be taken, and the associated account may be flagged for "
                    "repeated abuse."
                ),
            }
            return description_map[self]

        @classmethod
        def get_mandatory_remarks_statuses(cls) -> list:
            return [
                cls.ON_HOLD,
                cls.RESOLVED,
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

    # Preliminary AI screening signal. This never approves or rejects a report
    # on its own; staff still make the final decision. True when at least one
    # submitted image was flagged, and ai_flag_reasons lists the reason codes.
    # Once an officer reviews the flag, both this and the per-image flags are
    # cleared; the detection/review history lives in the audit trail.
    is_ai_flagged = models.BooleanField(default=False, db_index=True)
    ai_flag_reasons = models.JSONField(default=list, blank=True)

    # due date = date noted + category response time.
    # Null only for reports created before SLA tracking existed.
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True)

    # Set only when the reporter (citizen) confirms the completed works and
    # the report moves RESOLVED -> CLOSED. A CLOSED report with both
    # confirmed_at and auto_closed_at null was force-closed by staff (e.g.
    # out of DO 47 jurisdiction).
    confirmed_at = models.DateTimeField(null=True, blank=True)

    # Set only when the system closes a RESOLVED report after the configured
    # confirmation window elapses without the reporter responding. The report
    # keeps resolved_at for delivery metrics; confirmed_at stays null so an
    # automatic closure is never presented as a reporter confirmation.
    auto_closed_at = models.DateTimeField(null=True, blank=True)

    # Set once by the daily overdue job when the reporter is emailed that this
    # report has passed due_at. Never cleared: a report is notified at most
    # once in its lifetime, so re-running the job cannot send duplicates.
    overdue_notified_at = models.DateTimeField(null=True, blank=True, db_index=True)

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
