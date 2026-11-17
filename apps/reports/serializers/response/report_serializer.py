from typing import Any
from decimal import Decimal

from rest_framework import serializers

from apps.reports.models import (
    HazardReports,
    LEGACY_STATUS_ACTIVITY_LABELS,
    LEGACY_STATUS_TO_CODE,
    ReportImages,
)
from apps.audits.models import AuditLogs


def _status_code(value) -> str | None:
    """Normalize a status code or label to its upper-case code."""
    if not value:
        return None
    return str(value).strip().upper().replace(" ", "_").replace("-", "_")


def _legacy_activity_label(value) -> str | None:
    code = _status_code(value)
    return LEGACY_STATUS_ACTIVITY_LABELS.get(code)


def _staff_display_name(user) -> dict[str, str] | None:
    if not user:
        return None

    middle_name = f" {user.middle_name[0].upper()}." if user.middle_name else ""
    return {
        "email": user.email,
        "name": f"{user.last_name}, {user.first_name}{middle_name}",
    }


def _status_display(value) -> str | None:
    """Resolve a raw status code, a display label, or a retired status label.

    Older audit entries stored raw codes ("ON_HOLD") while newer ones store the
    display label ("On-Hold"); the timeline should render the same thing for
    both. Retired statuses (Under Review, Dispatched, Ongoing) collapse into
    In Progress and are surfaced as activities by the frontend.
    """
    if not value:
        return None

    code = _status_code(value)
    if code in LEGACY_STATUS_TO_CODE:
        code = LEGACY_STATUS_TO_CODE[code]

    try:
        return HazardReports.Status(code).label
    except ValueError:
        return value


class _ImageSignatureSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    signature = serializers.CharField()


class ReportImageSignatureResponseSerializer(serializers.Serializer):
    api_key = serializers.CharField()
    upload_url = serializers.URLField()
    upload_preset = serializers.CharField()
    asset_folder = serializers.CharField()
    use_asset_folder_as_public_id_prefix = serializers.BooleanField()
    timestamp = serializers.IntegerField()
    image_signatures = _ImageSignatureSerializer(many=True)


class CreateReportResponseSerializer(serializers.Serializer):
    report_number = serializers.CharField(min_length=20, max_length=20)
    reported_by = serializers.CharField()
    created_at = serializers.DateTimeField()


class GetReportListResponseSerializer(serializers.Serializer):
    #base/non-staff
    report_number = serializers.CharField(min_length=20, max_length=20)
    category = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    #DO 47 SLA (visible to both staff and citizens)
    due_at = serializers.DateTimeField(allow_null=True)
    is_overdue = serializers.BooleanField()

    # Staff-only: preliminary AI screening result. Advisory only; it marks the
    # report for manual review and never approves or rejects it. A reviewed
    # flag is cleared, so this is true only while the review is still pending.
    is_ai_flagged = serializers.BooleanField()
    ai_flag_reasons = serializers.ListField(child=serializers.CharField())

    #staff only
    severity = serializers.CharField(min_length=2, max_length=2)
    address = serializers.CharField(max_length=225)
    # Staff-only: resolution timestamp (null until RESOLVED) so the Analytics
    # module can compute average resolution time and SLA on-time rates from
    # the list response without extra detail calls.
    resolved_at = serializers.DateTimeField(allow_null=True)

    def get_category(self, value) -> str:
        return value.category.hazard_name

    def get_status(self, value) -> str:
        return HazardReports.Status(value.status).label

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context.get("user")

        if not user or not user.is_staff:
            data.pop("severity", None)
            data.pop("address", None)
            data.pop("resolved_at", None)
            data.pop("is_ai_flagged", None)
            data.pop("ai_flag_reasons", None)

        return data


class GetReportDetailResponseSerializer(serializers.Serializer):
    #base
    report_number = serializers.CharField(min_length=20, max_length=20)
    status = serializers.SerializerMethodField()

    latitude = serializers.DecimalField(
        max_digits=8,
        decimal_places=6,
        min_value=Decimal('-90.0'),
        max_value=Decimal('90.0')
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal('-180.0'),
        max_value=Decimal('180.0')
    )

    address = serializers.CharField(max_length=255)
    description = serializers.CharField()
    remarks = serializers.CharField()

    #DO 47 SLA (visible to both staff and citizens)
    due_at = serializers.DateTimeField(allow_null=True)
    is_overdue = serializers.BooleanField()

    #Citizen confirmation marker (visible to both): set when the reporter
    #closed the report; null on staff force-closes or non-closed reports.
    confirmed_at = serializers.DateTimeField(allow_null=True)

    #System auto-closure marker (visible to both): set when the 7-day
    #confirmation window expired without the reporter responding.
    auto_closed_at = serializers.DateTimeField(allow_null=True)

    image_urls = serializers.SerializerMethodField()

    #DO 47 photolog: grouped Before/During/After photos (visible to both)
    photos = serializers.SerializerMethodField()

    #non-staff only
    status_timeline = serializers.SerializerMethodField()
    next_expected_statuses = serializers.ListField(child=serializers.CharField())
    resolution_image_urls = serializers.SerializerMethodField()

    #staff only
    reported_by = serializers.SerializerMethodField()
    #moderation target: real reporter account even on anonymous reports
    #(anonymity is display-only; enforcement still needs the account)
    reported_by_user_number = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    validated_by_name = serializers.CharField(allow_null=True)
    validated_by = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    # Raw FK id so the edit modal can preselect the current category —
    # the `category` field above is only the display name.
    category_id = serializers.IntegerField()
    severity = serializers.CharField()
    created_at = serializers.DateTimeField()

    # Staff-only: preliminary AI screening result. Advisory only; a flagged
    # report still requires a human decision. Once reviewed, both the report
    # and per-image flags are cleared and the history moves to the timeline.
    is_ai_flagged = serializers.BooleanField()
    ai_flag_reasons = serializers.ListField(child=serializers.CharField())
    image_ai_flags = serializers.SerializerMethodField()

    def get_status(self, value) -> str:
        return HazardReports.Status(value.status).label

    def get_reported_by(self, value) -> str:
        if not value.is_anonymous:
            reported_by = value.reported_by

            middle_name = f" {reported_by.middle_name[0].upper()}." if reported_by.middle_name else ""
            full_name = f"{reported_by.last_name}, {reported_by.first_name}{middle_name}"

            return full_name

        return "<Anonymous>"

    def get_reported_by_user_number(self, value) -> str:
        return value.reported_by.user_number

    def get_assigned_to(self, value) -> dict | None:
        return _staff_display_name(value.assigned_to)

    def get_validated_by(self, value) -> dict | None:
        return _staff_display_name(value.validated_by)

    def get_category(self, value) -> str:
        return value.category.hazard_name

    def get_image_urls(self, value) -> list:
        return [
            image.image_url
            for image in value.images.all()
            if image.photo_type == ReportImages.PhotoType.BEFORE
        ]

    def get_image_ai_flags(self, value) -> list[dict]:
        return [
            {
                "image_url": image.image_url,
                "is_ai_flagged": image.is_ai_flagged,
            }
            for image in value.images.all()
            if image.photo_type == ReportImages.PhotoType.BEFORE
        ]

    def get_resolution_image_urls(self, value) -> list:
        return [
            image.image_url
            for image in value.images.all()
            if image.photo_type in (ReportImages.PhotoType.DURING, ReportImages.PhotoType.AFTER)
        ]

    def get_photos(self, value) -> dict:
        photos: dict[str, list[str]] = {"before": [], "during": [], "after": []}
        for image in value.images.all():
            photos[image.photo_type.lower()].append(image.image_url)
        return photos

    def get_status_timeline(self, value) -> list:
        # Order by timestamp, then by log id: the AI review is written in the
        # same second as the status change it accompanies, and the id keeps
        # that pair in the order the officer worked (review, then new status).
        audit_logs = sorted(
            (
                audit_log
                for audit_log in value.audit_logs.all()
                if audit_log.action in (
                    AuditLogs.ActionType.CREATE,
                    AuditLogs.ActionType.STATUS_CHANGE,
                    AuditLogs.ActionType.TRANSFER,
                    AuditLogs.ActionType.ACTIVITY_NOTE,
                )
            ),
            key=lambda audit_log: (audit_log.created_at, audit_log.audit_log_id),
        )
        status_timeline = []

        for audit_log in audit_logs:
            payload = audit_log.payload or {}
            activity_note = payload.get("activity_note") or {}
            status_change = payload.get("status_change") or {}
            initial_status = payload.get("initial_status")
            to_status = status_change.get("to")
            # ACTIVITY_NOTE entries do not change status; their payload carries
            # the status the report was in when the note was written.
            status = _status_display(
                initial_status
                or to_status
                or activity_note.get("status")
                or payload.get("status")
            ) or HazardReports.Status(value.status).label

            if audit_log.action == AuditLogs.ActionType.CREATE:
                from_status = None
                to_status = initial_status or status
            else:
                from_status = status_change.get("from")

            # Retired statuses become activities inside In Progress. Explicit
            # ACTIVITY_NOTE entries carry their own label from the payload.
            legacy_label = _legacy_activity_label(to_status or initial_status)
            activity_label = (
                activity_note.get("label")
                or payload.get("activity_label")
                or legacy_label
            )
            activity_code = activity_note.get("type") or payload.get("activity") or (
                _status_code(to_status or initial_status) if legacy_label else None
            )

            actor = audit_log.user
            status_timeline.append({
                "status": status,
                "created_at": audit_log.created_at.isoformat(),
                # Citizen-safe extras for the timeline's "View Details" dialog:
                # the actor's role only (never name/email) and the payload's
                # remarks for THIS change. The raw audit description is left
                # out on purpose — it embeds internal USR- numbers, and
                # TRANSFER payloads hold staff emails.
                "action": audit_log.action,
                "from_status": from_status,
                "to_status": to_status,
                "remarks": payload.get("remarks") or None,
                "performed_by_role": actor.role.role_name if actor and actor.role else None,
                "activity": activity_code,
                "activity_label": activity_label,
                "is_activity": bool(activity_label),
            })
        return status_timeline

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context.get("user")

        if user and user.is_staff:
            data.pop("status_timeline", None)
            # next_expected_statuses is kept for staff: the report management
            # modal restricts its status dropdown to the transition matrix.
            data.pop("resolution_image_urls", None)

        else:
            data.pop("reported_by", None)
            data.pop("reported_by_user_number", None)
            data.pop("assigned_to", None)
            data.pop("validated_by_name", None)
            data.pop("validated_by", None)
            data.pop("category", None)
            data.pop("category_id", None)
            data.pop("severity", None)
            data.pop("created_at", None)
            data.pop("is_ai_flagged", None)
            data.pop("ai_flag_reasons", None)
            data.pop("image_ai_flags", None)
            # Internal staff-only working notes; citizens only ever see the
            # per-transition remarks inside status_timeline.
            data.pop("remarks", None)

        return data


class GetReportHistoryDetailResponseSerializer(serializers.Serializer):
    report_number = serializers.CharField(min_length=20, max_length=20)
    address = serializers.CharField(max_length=225)
    severity = serializers.CharField()
    description = serializers.CharField()

    status = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    image_urls = serializers.SerializerMethodField()
    resolution_image_urls = serializers.SerializerMethodField()

    status_timeline = serializers.SerializerMethodField()

    def get_status(self, value) -> str:
        return HazardReports.Status(value.status).label

    def get_category(self, value) -> str:
        return value.category.hazard_name

    def get_image_urls(self, value) -> list[str]:
        return [
            image.image_url
            for image in value.images.all()
            if image.photo_type == ReportImages.PhotoType.BEFORE
        ]

    def get_resolution_image_urls(self, value) -> list[str]:
        return [
            image.image_url
            for image in value.images.all()
            if image.photo_type in (ReportImages.PhotoType.DURING, ReportImages.PhotoType.AFTER)
        ]

    def get_status_timeline(self, value) -> list[dict[str, Any]]:
        # Order by timestamp, then by log id: the AI review and the status
        # change it accompanies are written back-to-back, so the id breaks the
        # tie in insertion order (AI review first).
        audit_logs = sorted(
            (
                audit_log
                for audit_log in value.audit_logs.all()
                if audit_log.action in (
                    AuditLogs.ActionType.CREATE,
                    AuditLogs.ActionType.STATUS_CHANGE,
                    AuditLogs.ActionType.TRANSFER,
                    AuditLogs.ActionType.ACTIVITY_NOTE,
                    AuditLogs.ActionType.AI_FLAG_DETECTED,
                    AuditLogs.ActionType.AI_FLAG_REVIEW,
                )
            ),
            key=lambda audit_log: (audit_log.created_at, audit_log.audit_log_id),
        )
        status_timeline = []

        for audit_log in audit_logs:
            payload = audit_log.payload or {}
            activity_note = payload.get("activity_note") or {}
            # TRANSFER and AI-flag logs may carry something other than a
            # top-level status_change payload; fall back to the report's
            # current status when no status can be derived.
            ai_flag_review = payload.get("ai_flag_review") or {}
            review_status_change = ai_flag_review.get("status_change") or {}
            status_change = payload.get("status_change") or {}
            initial_status = payload.get("initial_status")
            to_status = status_change.get("to") or review_status_change.get("to")
            status = _status_display(
                initial_status
                or to_status
                or activity_note.get("status")
                or payload.get("status")
            ) or HazardReports.Status(value.status).label

            legacy_label = _legacy_activity_label(to_status or initial_status)
            activity_label = (
                activity_note.get("label")
                or payload.get("activity_label")
                or legacy_label
            )
            activity_code = activity_note.get("type") or payload.get("activity") or (
                _status_code(to_status or initial_status) if legacy_label else None
            )

            user = audit_log.user
            if user:
                if not user.is_staff and value.is_anonymous:
                    name = "<Anonymous>"

                else:
                    middle_name = f" {user.middle_name[0].upper()}." if user.middle_name else ""
                    name = f"{user.last_name}, {user.first_name}{middle_name}"

            else:
                name = "System"


            status_log_detail = {
                "audit_log_number": audit_log.audit_log_number,
                "module": f"{AuditLogs.ModuleType(audit_log.module).label} Management",
                "action": AuditLogs.ActionType(audit_log.action).label,
                "action_code": audit_log.action,
                "description": audit_log.description,
                "status": status,
                "created_at": audit_log.created_at.isoformat(),
                "from_status": status_change.get("from"),
                "to_status": to_status,
                "remarks": payload.get("remarks") or None,
                "activity": activity_code,
                "activity_label": activity_label,
                "is_activity": bool(activity_label),
                "performed_by": {
                    "name": name,
                    "role": user.role.role_name if user else None
                }
            }

            status_timeline.append(status_log_detail)

        return status_timeline