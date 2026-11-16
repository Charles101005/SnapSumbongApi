from django.db import models


class ReportActivity(models.TextChoices):
    """Activities recorded inside the In Progress/On-Hold handling phase.

    These are not ticket statuses: logging one never changes
    HazardReports.status. They give dispatch, field work, and coordination
    their own timestamped history now that those stages no longer exist as
    independent statuses.

    VALIDATED is retained for historical audit rows (old Under Review entries
    were mapped to it) but is no longer selectable: entering In Progress is the
    validation milestone. Offering it again would create duplicate
    "Report validated" entries.
    """

    VALIDATED = "VALIDATED", "Report validated"
    DISPATCHED = "DISPATCHED", "Forwarded to field personnel"
    WORK_STARTED = "WORK_STARTED", "Corrective work started"
    WORK_COMPLETED = "WORK_COMPLETED", "Corrective work completed"
    REFERRED = "REFERRED", "Referred to another office or agency"
    FOLLOW_UP = "FOLLOW_UP", "Follow-up update"
    NOTE = "NOTE", "General update"


REPORT_ACTIVITY_VALUES = tuple(choice.value for choice in ReportActivity)

# New activity notes may not use VALIDATED; the Assigned -> In Progress
# transition already records validation. Keep it in the label map below so old
# audit rows still render correctly.
REPORT_ACTIVITY_SELECTABLE_VALUES = tuple(
    choice.value for choice in ReportActivity
    if choice != ReportActivity.VALIDATED
)

REPORT_ACTIVITY_LABELS = {
    choice.value: choice.label for choice in ReportActivity
}
