import logging
import secrets
from typing import Any
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from django.db.models import QuerySet, Q
from django.conf import settings

from apps.accounts.models import Users, CitizenWarnings
from shared.results import DomainResult
from external.storage import StorageService, UploadIntent
from apps.reports.models import (
    HazardReports,
    HazardCategories,
    ReportImages,
    STATUS_ALLOWED_TRANSITIONS,
)
from apps.reports.constants import (
    AI_FLAG_DECISION_CLEARED,
    AI_FLAG_DECISION_CONFIRMED,
    AI_FLAG_DECISIONS,
    REPORT_ACTIVITY_SELECTABLE_VALUES,
    ReportActivity,
)
from apps.reports.exceptions.report_exception import (
    InvalidImageCountException,
    InvalidHazardCategoryException,
    ReportDoesNotExistException,
    InvalidReportStatusException,
    InvalidReportSeverityException,
    InvalidAiFlagDecisionException,
    InvalidReportActivityException,
)
from apps.reports.domain_errors.report_error import (
    DuplicateStatusTransitionError,
    InvalidReportUpdateError,
    StatusResolutionImageConflictError,
    MandatoryRemarksStatusError,
    AssignedStatusTransitionError,
    StatusTransitionNotAllowedError,
    ActivityRemarksRequiredError,
    ActivityRemarksWithoutActivityError,
    ReferralRequiresOnHoldError,
    ReportActivityNotPermittedError,
    MandatorySeverityStatusError,
    ResolutionImageRequiredError,
    MissingDuringPhotoError,
    MissingAfterPhotoError,
    ReportNotResolvedError,
    ReportNotReopenableError,
    ReopenRemarksRequiredError,
    ValidatorNameRequiredError,
    ReportNotTransferableError,
    InvalidTransferTargetError,
    AlreadyAssignedToTargetError,
    CategoryChangeNotPermittedError,
    MandatoryCategoryRemarksError,
    ReportBlockedByWarningsError,
    AiFlagReviewRequiredError,
    AiFlagReviewUnavailableError,
    AiFlagDecisionStatusMismatchError,
)
from apps.accounts.services import UserService
from apps.accounts.services.moderation_service import BAN_WARNING_THRESHOLD
from apps.audits.services import AuditLogService
from shared.authorization.service import AuthorizationService
from shared.authorization import AllPermissions
from external.email import EmailService
from external.ai import AIService


# Transitions that require the officer to answer the advisory AI screening
# question. In Progress is included deliberately: an AI-flagged report must be
# reviewed before it enters handling, not only when it later leaves it. The
# same decision also covers every later target, so the flag never survives
# into In Progress on a new report.
AI_FLAG_REVIEW_REQUIRED_TARGETS = {
    HazardReports.Status.IN_PROGRESS.value,
    HazardReports.Status.ON_HOLD.value,
    HazardReports.Status.RESOLVED.value,
    HazardReports.Status.CLOSED.value,
    HazardReports.Status.INVALID.value,
}


logger = logging.getLogger(__name__)


class ReportService:
    @staticmethod
    def _format_datetime(value) -> str:
        return timezone.localtime(value).strftime("%B %d, %Y at %I:%M %p")

    @staticmethod
    def _reporter_can_be_notified(report: HazardReports) -> bool:
        # Anonymous reports stay anonymous to other users only -- the reporter
        # still gets updates on their own submission. Report notifications are
        # also preference-based: the user can opt out via is_notified=False.
        return bool(report.reported_by and report.reported_by.is_notified)

    @staticmethod
    def _enqueue_status_update_email(
            *,
            report: HazardReports,
            old_status_label: str,
            new_status_label: str,
            remarks: str = ""
    ) -> None:
        if not ReportService._reporter_can_be_notified(report):
            return

        transaction.on_commit(
            lambda r=report, o=old_status_label, n=new_status_label, rem=remarks:
                EmailService.send_report_status_update(
                    to_email=r.reported_by.email,
                    to_first_name=r.reported_by.first_name,
                    report_number=r.report_number,
                    category=r.category.hazard_name,
                    location=r.address,
                    submitted_at=ReportService._format_datetime(r.created_at),
                    old_status=o,
                    new_status=n,
                    remarks=rem,
                )
        )

    @staticmethod
    @transaction.atomic
    def _process_unassigned_reports() -> None:
        unassigned_active_reports: list = list(
            HazardReports.objects.filter(
                status=HazardReports.Status.NEW,
                assigned_to__isnull=True,
            ).order_by('created_at').select_for_update(skip_locked=True)[:5]
        )

        if not unassigned_active_reports:
            return

        for report in unassigned_active_reports:
            assigned_staff = ReportService._get_next_report_assigned_to()

            if not assigned_staff:
                return

            report.assigned_to = assigned_staff

            old_status = HazardReports.Status(report.status)
            report.status = HazardReports.Status.ASSIGNED

            report.save(update_fields=[
                'assigned_to',
                'status',
            ])

            AuditLogService.log_report_status_change(
                actor=None,
                old_status=old_status.label,
                new_status=report.status.label,
                report=report
            )

    @staticmethod
    def _get_next_report_assigned_to():
        assigned_staff = UserService.get_next_staff_for_assignment()

        if assigned_staff:
            # Advance the round-robin pointer: the handler who has gone
            # longest without an assignment is picked next.
            assigned_staff.assigned_at = timezone.now()
            assigned_staff.save(update_fields=["assigned_at"])

        return assigned_staff

    @staticmethod
    def _has_reached_warning_limit(*, user_id: int) -> bool:
        # Citizens at or above the ban threshold are no longer allowed to
        # report, even if moderation has not banned the account yet.
        return CitizenWarnings.objects.filter(user_id=user_id).count() >= BAN_WARNING_THRESHOLD

    @staticmethod
    def _authorized_reports(user: Users) -> QuerySet[HazardReports]:
        if AuthorizationService.has_perm(user, AllPermissions.REPORTS.READ_ALL):
            queryset = HazardReports.objects.all()

        elif AuthorizationService.has_perm(user, AllPermissions.REPORTS.READ_ASSIGNED):
            queryset = HazardReports.objects.filter(assigned_to_id=user.user_id)

        else:
            queryset = HazardReports.objects.filter(reported_by_id=user.user_id)

        return queryset

    @staticmethod
    def get_status_list() -> DomainResult[list[dict[str, Any]]]:
        return DomainResult.success(
            [
                {
                    "label": status.label,
                    "value": status.value,
                    "description": status.description,
                    "is_terminal": status.is_terminal,
                }
                for status in HazardReports.Status
            ]
        )

    @staticmethod
    def get_severity_list() -> DomainResult[list[str]]:
        return DomainResult.success([severity.value for severity in HazardReports.Severity])

    @staticmethod
    def get_hazard_image_upload_credentials(
            *,
            user: Users,
            image_count: int
    ) -> DomainResult[dict[str, Any]]:
        if image_count <= 0 or image_count > settings.STORAGE_CONFIG["MAX_SIGNATURE_COUNT"]:
            raise InvalidImageCountException()

        if AuthorizationService.has_perm(user, AllPermissions.REPORTS.UPDATE_ASSIGNED):
            intent: UploadIntent = UploadIntent.REPORT_RESOLUTION
        else:
            # Only citizen report uploads are gated; officers requesting
            # resolution-image signatures must still be able to work.
            if ReportService._has_reached_warning_limit(user_id=user.user_id):
                return DomainResult.error(ReportBlockedByWarningsError)

            intent: UploadIntent = UploadIntent.HAZARD_REPORTS

        now = timezone.now()
        folder_path = f"{intent.value}/{now.strftime('%Y')}/{now.strftime('%m')}"

        batch_id = secrets.token_urlsafe(16)
        file_names = [f"{batch_id}_img{i}" for i in range(1, image_count + 1)]

        upload_credentials = StorageService.get_upload_credentials(
            folder_path=folder_path,
            file_names=file_names,
            intent=intent
        )

        return DomainResult.success(upload_credentials)

    @staticmethod
    def _screen_report_images(
            *,
            image_urls: list[str],
            category_name: str,
            description: str,
    ) -> dict[str, Any]:
        """Run the preliminary AI image screening.

        The result is advisory only: it flags images for manual review and
        never approves or rejects a report. When screening is disabled or the
        AI call fails, the report is submitted unflagged (fail open).
        """
        no_flags = {
            "images": {},
            "is_flagged": False,
            "ai_flag_reasons": [],
        }

        if not settings.AI_IMAGE_SCREENING_ENABLED or not image_urls:
            return no_flags

        try:
            result = AIService.validate_report_images(
                image_urls=image_urls,
                category=category_name,
                description=description,
            )
        except Exception:
            return no_flags

        if not result.get("success"):
            return no_flags

        images = {
            image["image_url"]: image
            for image in result.get("images", [])
        }

        return {
            "images": images,
            "is_flagged": bool(result.get("is_flagged")),
            "ai_flag_reasons": list(result.get("flagged_reasons") or []),
        }

    @staticmethod
    def create_assign_hazard_report(
            *,
            reported_by_id: int,
            category_id: int,
            latitude: Decimal,
            longitude: Decimal,
            address: str,
            description: str,
            is_anonymous: bool,
            image_urls: list[str],
    ) -> DomainResult[HazardReports]:
        if ReportService._has_reached_warning_limit(user_id=reported_by_id):
            return DomainResult.error(ReportBlockedByWarningsError)

        category = HazardCategories.objects.get_by_id_or_none(category_id)

        if not category:
            raise InvalidHazardCategoryException()

        # Preliminary AI screening runs before the transaction starts so a slow
        # model call never holds database locks. It is advisory only, so a
        # failure here never blocks submission; it just flags images for
        # manual review.
        screening = ReportService._screen_report_images(
            image_urls=image_urls,
            category_name=category.hazard_name,
            description=description,
        )

        return ReportService._persist_hazard_report(
            reported_by_id=reported_by_id,
            category=category,
            latitude=latitude,
            longitude=longitude,
            address=address,
            description=description,
            is_anonymous=is_anonymous,
            image_urls=image_urls,
            screening=screening,
        )

    @staticmethod
    @transaction.atomic
    def _persist_hazard_report(
            *,
            reported_by_id: int,
            category: HazardCategories,
            latitude: Decimal,
            longitude: Decimal,
            address: str,
            description: str,
            is_anonymous: bool,
            image_urls: list[str],
            screening: dict[str, Any],
    ) -> DomainResult[HazardReports]:
        ReportService._process_unassigned_reports()

        assigned_staff = ReportService._get_next_report_assigned_to()
        initial_status = HazardReports.Status.ASSIGNED if assigned_staff else HazardReports.Status.NEW

        now = timezone.now()
        due_at = now + timedelta(days=category.response_time_days)

        report: HazardReports = HazardReports.objects.create(
            reported_by_id=reported_by_id,
            assigned_to=assigned_staff,
            category=category,
            latitude=latitude,
            longitude=longitude,
            address=address,
            description=description,
            status=initial_status,
            is_anonymous=is_anonymous,
            due_at=due_at,
            is_ai_flagged=screening["is_flagged"],
            ai_flag_reasons=screening["ai_flag_reasons"],
        )

        for image_url in image_urls:
            image_screening = screening["images"].get(image_url) or {}

            report.images.create(
                image_url=image_url,
                photo_type=ReportImages.PhotoType.BEFORE,
                is_ai_flagged=bool(image_screening.get("is_flagged", False)),
            )

        AuditLogService.log_create(
            actor=report.reported_by,
            module=AuditLogService.ModuleType.REPORT,
            target_object=report,
            target_identifier=report.report_number,
            payload={
                "initial_status": report.status.label,
                "assigned_to": assigned_staff.email if assigned_staff else None,
            },
        )

        # The screening result is advisory, but its detection is still part of
        # the report's story: log it so the staff timeline can show when and
        # why the report was flagged, even after the flags are reviewed away.
        if report.is_ai_flagged:
            AuditLogService.log_report_ai_flag_detected(report=report)

        # Report receipts are preference-based: users who opted out of
        # notifications (is_notified=False) don't get them.
        if ReportService._reporter_can_be_notified(report):
            transaction.on_commit(
                lambda r=report: EmailService.send_report_successful_submission(
                    to_email=r.reported_by.email,
                    to_first_name=r.reported_by.first_name,
                    report_number=r.report_number,
                    category=r.category.hazard_name,
                    location=r.address,
                    submitted_at=ReportService._format_datetime(r.created_at),
                )
            )

        return DomainResult.success(report)

    @staticmethod
    def list_authorized_reports(
            *,
            user: Users,
            query_filters: dict[str, Any]
    ) -> DomainResult[HazardReports]:
        authorized_reports = ReportService._authorized_reports(user=user)

        is_exclude_closed = query_filters.get("exclude_closed")
        if is_exclude_closed:
            closed_statuses = [status for status in HazardReports.Status if status.phase == 4]

            authorized_reports = authorized_reports.exclude(status__in=closed_statuses)

        queryset = authorized_reports.select_related("category")

        filter_map = {
            "category_id": "category__hazard_id",
            "status": "status__iexact",
            "created_at": "created_at__date",
            "severity": "severity__iexact",
            "from_date": "created_at__date__gte",
            "to_date": "created_at__date__lte",
        }

        filters = {
            filter_map[key]: value
            for key, value in query_filters.items()
            if key in filter_map and value is not None
        }

        if filters:
            queryset = queryset.filter(**filters)

        if query_filters.get("overdue"):
            open_statuses = [status.value for status in HazardReports.Status if status.phase < 4]
            queryset = queryset.filter(
                status__in=open_statuses,
                due_at__isnull=False,
                due_at__lt=timezone.now(),
            )

        search_query = query_filters.get("q")
        if search_query:
            search_terms = search_query.strip().split()

            for term in search_terms:
                queryset = queryset.filter(
                    Q(report_number__icontains=term) |
                    Q(category__hazard_name__icontains=term) |
                    Q(address__icontains=term)
                )

        return DomainResult.success(queryset.order_by("-created_at"))

    @staticmethod
    def get_authorized_reports(
            *,
            user: Users,
            report_number: str
    ) -> DomainResult[HazardReports]:
        authorized_reports = ReportService._authorized_reports(user=user)

        report = authorized_reports.filter(
            report_number__iexact=report_number
        ).select_related(
            "reported_by",
            "category",
            "assigned_to",
            "validated_by",
        ).prefetch_related(
            "images",
            "audit_logs",
            "audit_logs__user",
            "audit_logs__user__role"
        ).first()

        if not report:
            raise ReportDoesNotExistException()

        report.next_expected_statuses = HazardReports.Status(report.status).get_next_expected_statuses()

        return DomainResult.success(report)

    @staticmethod
    @transaction.atomic
    def update_authorized_assigned_report(
            *,
            user: Users,
            report_number: str,
            new_status_str: str|None=None,
            new_severity_str: str|None=None,
            new_category_id: int|None=None,
            remarks: str|None=None,
            resolution_images: list[dict]|None=None,
            validated_by_name: str|None=None,
            ai_flag_decision: str|None=None,
            activity: str|None=None,
            activity_remarks: str|None=None,
    ) -> DomainResult[None]:
        authorized_reports = ReportService._authorized_reports(user=user)

        report = authorized_reports.filter(report_number__iexact=report_number).first()
        if not report:
            raise ReportDoesNotExistException()

        updated_fields: list[str] = []

        new_status_str = new_status_str.strip().upper() if new_status_str else None
        new_severity_str = new_severity_str.strip().upper() if new_severity_str else None
        remarks = remarks.strip() if remarks else None
        ai_flag_decision = ai_flag_decision.strip().upper() if ai_flag_decision else None
        activity = activity.strip().upper() if activity else None
        activity_remarks = activity_remarks.strip() if activity_remarks else None

        if ai_flag_decision and ai_flag_decision not in AI_FLAG_DECISIONS:
            raise InvalidAiFlagDecisionException()

        if activity and activity not in REPORT_ACTIVITY_SELECTABLE_VALUES:
            raise InvalidReportActivityException()

        if activity_remarks and not activity:
            return DomainResult.error(ActivityRemarksWithoutActivityError)

        # A flag exists only until an officer reviews it: clearing the report
        # (and image) flags on either decision is what makes it "not pending".
        ai_flag_pending = report.is_ai_flagged

        if ai_flag_decision and not ai_flag_pending:
            return DomainResult.error(AiFlagReviewUnavailableError)

        # Remarks are allowed without a status change only when they accompany
        # a category correction, an AI review decision, or an explicit activity
        # note. A bare remark would otherwise be lost from the status history.
        if activity:
            activity_statuses = {
                HazardReports.Status.IN_PROGRESS.value,
                HazardReports.Status.ON_HOLD.value,
            }
            # Activities belong to the live handling phase. Validate the status
            # the report will have after this same save applies, so an activity
            # can never ride along with a Resolved/Closed/Invalid transition.
            resulting_status = new_status_str or report.status
            if resulting_status not in activity_statuses:
                return DomainResult.error(ReportActivityNotPermittedError)

            if not activity_remarks:
                return DomainResult.error(ActivityRemarksRequiredError)

            # A referral is an On-Hold condition (waiting on another office),
            # not an In Progress field note.
            if (
                activity == ReportActivity.REFERRED.value
                and resulting_status != HazardReports.Status.ON_HOLD.value
            ):
                return DomainResult.error(ReferralRequiresOnHoldError)

        if (
            remarks
            and not new_status_str
            and not new_category_id
            and not ai_flag_decision
            and not activity
        ) or (resolution_images and not new_status_str):
            return DomainResult.error(InvalidReportUpdateError)

        # Validated against the status as the request found it (before any
        # transition below applies): the category is only editable while the
        # report sits in In Progress — the handling stage where a misclassified
        # citizen submission gets caught.
        if new_category_id is not None:
            if HazardReports.Status(report.status) != HazardReports.Status.IN_PROGRESS:
                return DomainResult.error(CategoryChangeNotPermittedError)

            if not remarks:
                return DomainResult.error(MandatoryCategoryRemarksError)

            if new_category_id != report.category_id:
                new_category = HazardCategories.objects.get_by_id_or_none(new_category_id)
                if not new_category:
                    raise InvalidHazardCategoryException()

                old_category_name = report.category.hazard_name
                old_due_at = report.due_at

                report.category = new_category
                updated_fields.append("category")

                # DO 47 s.2024 §4.1: the SLA clock stays anchored to report
                # creation (when the defect was noted) and runs for the
                # corrected category's response time. A shorter window may
                # land in the past — flagged Overdue retroactively on purpose:
                # the defect has in fact been known longer than the corrected
                # category allows.
                report.due_at = report.created_at + timedelta(days=new_category.response_time_days)
                updated_fields.append("due_at")

                # Keep the report's latest-reason field in sync with the
                # category correction (the audit entry already carries it).
                report.remarks = remarks
                if "remarks" not in updated_fields:
                    updated_fields.append("remarks")

                AuditLogService.log_report_category_change(
                    actor=user,
                    old_category=old_category_name,
                    new_category=new_category.hazard_name,
                    remarks=remarks,
                    old_due_at=old_due_at,
                    new_due_at=report.due_at,
                    report=report,
                )

        status_changed = False
        old_status_label = None

        if new_status_str:
            if new_status_str not in HazardReports.Status:
                raise InvalidReportStatusException()

            if new_status_str == report.status:
                return DomainResult.error(DuplicateStatusTransitionError)

            # The AI screening flag is advisory: when a flagged report enters
            # handling, the officer must say whether the report is valid. The
            # original flag/reasons are retained and the decision is audited.
            if ai_flag_decision == AI_FLAG_DECISION_CONFIRMED and new_status_str != HazardReports.Status.INVALID.value:
                return DomainResult.error(AiFlagDecisionStatusMismatchError)

            if ai_flag_decision == AI_FLAG_DECISION_CLEARED and new_status_str == HazardReports.Status.INVALID.value:
                return DomainResult.error(AiFlagDecisionStatusMismatchError)

            if (
                ai_flag_pending
                and not ai_flag_decision
                and new_status_str in AI_FLAG_REVIEW_REQUIRED_TARGETS
            ):
                return DomainResult.error(AiFlagReviewRequiredError)

            # A confirmed AI flag is the one triage verdict that may skip
            # In Progress: the reviewer has already judged the report fake, so
            # Assigned can go straight to Invalid in the same save. The
            # transition matrix stays unchanged for unflagged reports.
            ai_confirmed_invalid = (
                report.status == HazardReports.Status.ASSIGNED
                and new_status_str == HazardReports.Status.INVALID.value
                and ai_flag_decision == AI_FLAG_DECISION_CONFIRMED
            )

            if new_status_str in HazardReports.Status.get_mandatory_remarks_statuses() and not remarks:
                return DomainResult.error(MandatoryRemarksStatusError)

            # Assigned normally has exactly one next stage: In Progress.
            # Enforced here so the rule holds no matter how the PATCH is sent.
            if (
                report.status == HazardReports.Status.ASSIGNED
                and new_status_str != HazardReports.Status.IN_PROGRESS
                and not ai_confirmed_invalid
            ):
                return DomainResult.error(AssignedStatusTransitionError)

            # The transition matrix is the single source of truth for legal
            # status moves. Enforcing it server-side keeps the API from
            # creating stages the UI (and the citizen timeline) cannot render.
            current_status_value = HazardReports.Status(report.status).value
            allowed_next = STATUS_ALLOWED_TRANSITIONS.get(current_status_value, ())
            if new_status_str not in allowed_next and not ai_confirmed_invalid:
                return DomainResult.error(StatusTransitionNotAllowedError)

            # Severity is the triage verdict made when handling starts: it
            # must already exist or be supplied in this same update before the
            # report enters In Progress, and remains required before moving to
            # On-Hold or Resolved. Flagging Invalid stays exempt — that is a
            # moderation verdict, not a triage one.
            if (
                report.status == HazardReports.Status.ASSIGNED
                and new_status_str == HazardReports.Status.IN_PROGRESS
                and not (new_severity_str or report.severity)
            ):
                return DomainResult.error(MandatorySeverityStatusError)

            if (
                report.status == HazardReports.Status.IN_PROGRESS
                and new_status_str in (
                    HazardReports.Status.ON_HOLD,
                    HazardReports.Status.RESOLVED,
                )
                and not (new_severity_str or report.severity)
            ):
                return DomainResult.error(MandatorySeverityStatusError)

            old_status = HazardReports.Status(report.status)
            old_status_label = old_status.label
            report.status = HazardReports.Status(new_status_str)
            status_changed = True
            updated_fields.append("status")

            # A manual New -> Assigned move (e.g. an admin picking up an
            # unassigned report) should also make the actor the custodian;
            # otherwise the report would be "Assigned" to nobody.
            if (
                new_status_str == HazardReports.Status.ASSIGNED.value
                and not report.assigned_to_id
            ):
                report.assigned_to = user
                updated_fields.append("assigned_to")

            report.remarks = remarks
            if "remarks" not in updated_fields:
                updated_fields.append("remarks")

            if new_status_str == HazardReports.Status.RESOLVED:
                # DO 47 s.2024 Appendix A-8: the Documentation Photolog must
                # show the rectification as During (works in progress) and
                # After (completed) photos. Before photos come from the
                # citizen's original submission.
                if not resolution_images:
                    return DomainResult.error(ResolutionImageRequiredError)

                photo_types = {image["photo_type"] for image in resolution_images}

                if ReportImages.PhotoType.DURING not in photo_types:
                    return DomainResult.error(MissingDuringPhotoError)

                if ReportImages.PhotoType.AFTER not in photo_types:
                    return DomainResult.error(MissingAfterPhotoError)

                # DO 47 s.2024 §2: the resolving officer declares the name of
                # the technical personnel who validated the completed works.
                # The assigned handler may resolve their own report as long
                # as this name is recorded (any name is accepted).
                validated_by_name = (validated_by_name or "").strip()
                if not validated_by_name:
                    return DomainResult.error(ValidatorNameRequiredError)

                report.validated_by_name = validated_by_name
                updated_fields.append("validated_by_name")

                report.validated_by = user
                updated_fields.append("validated_by")

                report.resolved_at = timezone.now()
                updated_fields.append("resolved_at")

                for image in resolution_images:
                    report.images.create(
                        image_url=image["image_url"],
                        photo_type=image["photo_type"],
                    )
            else:
                if resolution_images:
                    return DomainResult.error(StatusResolutionImageConflictError)

            ReportService._enqueue_status_update_email(
                report=report,
                old_status_label=old_status.label,
                new_status_label=report.status.label,
                remarks=remarks or "",
            )

        if ai_flag_decision:
            # Log the review while the evidence is still flagged, then clear
            # both the report and per-image flags. The report goes back to
            # looking like a normal submission; the timeline keeps the history.
            # This is written before the status-change entry so the timeline
            # reads "flagged -> reviewed -> new status" in the order the
            # officer actually worked.
            AuditLogService.log_report_ai_flag_review(
                actor=user,
                report=report,
                decision=ai_flag_decision,
                old_status=old_status_label if status_changed else None,
                new_status=report.status.label if status_changed else None,
                remarks=remarks,
            )

            report.is_ai_flagged = False
            updated_fields.append("is_ai_flagged")
            report.images.filter(is_ai_flagged=True).update(is_ai_flagged=False)

        if status_changed:
            AuditLogService.log_report_status_change(
                actor=user,
                old_status=old_status_label,
                new_status=report.status.label,
                remarks=remarks,
                report=report
            )

        if new_severity_str:
            if new_severity_str not in HazardReports.Severity:
                raise InvalidReportSeverityException()

            old_severity = report.severity
            report.severity = new_severity_str
            updated_fields.append("severity")

            AuditLogService.log_report_severity_change(
                actor=user,
                old_severity=old_severity,
                new_severity=report.severity,
                report=report
            )

        if activity:
            # Activities are notes inside the handling phase, not ticket
            # transitions. The activity note has its own remark so it never
            # overwrites a status-change remark in the audit trail.
            if not status_changed or not remarks:
                report.remarks = activity_remarks
                if "remarks" not in updated_fields:
                    updated_fields.append("remarks")

            AuditLogService.log_report_activity(
                actor=user,
                report=report,
                activity=activity,
                remarks=activity_remarks,
            )

        if updated_fields:
            report.save(update_fields=updated_fields)

        return DomainResult.success(None)

    @staticmethod
    @transaction.atomic
    def transfer_report(
            *,
            user: Users,
            report_number: str,
            assigned_to_user_number: str,
            remarks: str|None=None
    ) -> DomainResult[None]:
        authorized_reports = ReportService._authorized_reports(user=user)

        report = authorized_reports.filter(
            report_number__iexact=report_number
        ).select_for_update().first()
        if not report:
            raise ReportDoesNotExistException()

        if HazardReports.Status(report.status).phase >= 4:
            return DomainResult.error(ReportNotTransferableError)

        # Eligible targets mirror the auto-assignment pool: active staff
        # whose role can update assigned reports.
        target_staff = Users.objects.filter(
            user_number__iexact=assigned_to_user_number.strip(),
            is_staff=True,
            is_active=True,
            role__permissions__permission_name=AllPermissions.REPORTS.UPDATE_ASSIGNED.name,
        ).distinct().first()

        if not target_staff:
            return DomainResult.error(InvalidTransferTargetError)

        if report.assigned_to_id == target_staff.user_id:
            return DomainResult.error(AlreadyAssignedToTargetError)

        previous_assignee = report.assigned_to
        report.assigned_to = target_staff
        # Status is intentionally left unchanged: a transfer is a handoff,
        # not a workflow transition.
        report.save(update_fields=["assigned_to"])

        AuditLogService.log_report_transfer(
            actor=user,
            previous_assignee=previous_assignee,
            new_assignee=target_staff,
            remarks=remarks,
            report=report
        )

        return DomainResult.success(None)

    @staticmethod
    @transaction.atomic
    def confirm_report_resolution(*, user: Users, report_number: str) -> DomainResult[None]:
        # Citizen confirmation path to CLOSED: only the reporter can close
        # their own report, and only after it has been resolved (works done
        # + DO 47 validation). Staff force-closing (e.g. out of DO 47
        # jurisdiction) goes through update_authorized_assigned_report
        # instead and leaves confirmed_at null.
        report = HazardReports.objects.filter(
            reported_by_id=user.user_id,
            report_number__iexact=report_number,
        ).first()
        if not report:
            raise ReportDoesNotExistException()

        if report.status != HazardReports.Status.RESOLVED:
            return DomainResult.error(ReportNotResolvedError)

        old_status = HazardReports.Status(report.status)
        report.status = HazardReports.Status.CLOSED
        report.confirmed_at = timezone.now()
        report.save(update_fields=["status", "confirmed_at"])

        AuditLogService.log_report_status_change(
            actor=user,
            old_status=old_status.label,
            new_status=report.status.label,
            remarks="Resolution confirmed by the reporter.",
            report=report,
        )

        ReportService._enqueue_status_update_email(
            report=report,
            old_status_label=old_status.label,
            new_status_label=report.status.label,
        )

        return DomainResult.success(None)

    @staticmethod
    @transaction.atomic
    def reopen_report_by_reporter(
            *,
            user: Users,
            report_number: str,
            remarks: str | None = None,
    ) -> DomainResult[None]:
        """Reopen a resolved report from the reporter's own view.

        This is the citizen counterpart to the staff update path. It is
        deliberately separate from the status matrix: only the reporter may
        reopen their own resolved report, and the reason is mandatory. Closed
        reports are final and are intentionally not reopenable.
        """
        report = HazardReports.objects.filter(
            reported_by_id=user.user_id,
            report_number__iexact=report_number,
        ).first()
        if not report:
            raise ReportDoesNotExistException()

        if report.status != HazardReports.Status.RESOLVED:
            return DomainResult.error(ReportNotReopenableError)

        remarks = remarks.strip() if remarks else None
        if not remarks or len(remarks) < 10:
            return DomainResult.error(ReopenRemarksRequiredError)

        old_status = HazardReports.Status(report.status)
        report.status = HazardReports.Status.IN_PROGRESS
        report.resolved_at = None
        report.confirmed_at = None
        report.auto_closed_at = None
        report.validated_by = None
        report.validated_by_name = None
        report.remarks = remarks
        report.save(update_fields=[
            "status",
            "resolved_at",
            "confirmed_at",
            "auto_closed_at",
            "validated_by",
            "validated_by_name",
            "remarks",
        ])

        AuditLogService.log_report_status_change(
            actor=user,
            old_status=old_status.label,
            new_status=report.status.label,
            remarks=remarks,
            report=report,
            description_override=(
                f"REPORT {report.report_number} was reopened by "
                f"{user.user_number} with the remarks: \"{remarks}\""
            ),
        )

        ReportService._enqueue_status_update_email(
            report=report,
            old_status_label=old_status.label,
            new_status_label=report.status.label,
            remarks=remarks,
        )

        return DomainResult.success(None)

    @staticmethod
    def auto_close_resolved_reports(
            *,
            older_than_days: int | None = None,
            dry_run: bool = False,
            batch_size: int = 500,
    ) -> dict[str, int]:
        """Close RESOLVED reports whose confirmation window has elapsed.

        A report is eligible only when it has a resolved_at timestamp, the
        reporter has not confirmed it, and the configured number of days has
        passed. The report keeps resolved_at for delivery metrics; the new
        auto_closed_at timestamp records why it closed.

        Each report is handled in its own transaction. Re-checking the status
        after locking keeps a citizen confirmation or a staff closure that
        happens during the run from being overwritten.
        """
        days = (
            older_than_days
            if older_than_days is not None
            else settings.REPORT_CONFIG.get('RESOLVED_AUTO_CLOSE_AFTER_DAYS', 7)
        )
        if days < 0:
            raise ValueError("older_than_days must be zero or greater.")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")

        cutoff = timezone.now() - timedelta(days=days)
        reason = (
            f"Automatically closed after {days} days without reporter confirmation."
        )

        eligible = HazardReports.objects.filter(
            status=HazardReports.Status.RESOLVED,
            resolved_at__isnull=False,
            resolved_at__lte=cutoff,
            confirmed_at__isnull=True,
        ).order_by("report_id")

        if dry_run:
            return {
                "closed": 0,
                "skipped": 0,
                "failed": 0,
                "would_close": eligible.count(),
            }

        closed = 0
        skipped = 0
        failed = 0
        last_id = 0

        while True:
            report_ids = list(
                eligible.filter(report_id__gt=last_id)
                .values_list("report_id", flat=True)[:batch_size]
            )
            if not report_ids:
                break

            for report_id in report_ids:
                last_id = report_id
                try:
                    with transaction.atomic():
                        report = (
                            HazardReports.objects.select_for_update()
                            .filter(report_id=report_id)
                            .first()
                        )
                        if (
                            not report
                            or report.status != HazardReports.Status.RESOLVED
                            or report.resolved_at is None
                            or report.resolved_at > cutoff
                            or report.confirmed_at is not None
                        ):
                            skipped += 1
                            continue

                        report.status = HazardReports.Status.CLOSED
                        report.auto_closed_at = timezone.now()
                        report.save(update_fields=["status", "auto_closed_at"])

                        AuditLogService.log_report_status_change(
                            actor=None,
                            old_status=HazardReports.Status.RESOLVED.label,
                            new_status=HazardReports.Status.CLOSED.label,
                            remarks=reason,
                            report=report,
                            description_override=(
                                f"REPORT {report.report_number} was automatically "
                                f"closed by the System after {days} days without "
                                "reporter confirmation."
                            ),
                        )

                        ReportService._enqueue_status_update_email(
                            report=report,
                            old_status_label=HazardReports.Status.RESOLVED.label,
                            new_status_label=HazardReports.Status.CLOSED.label,
                            remarks=reason,
                        )
                    closed += 1
                except Exception:
                    logger.exception(
                        "Failed to auto-close report_id=%s", report_id
                    )
                    failed += 1

        return {
            "closed": closed,
            "skipped": skipped,
            "failed": failed,
            "would_close": 0,
        }

    @staticmethod
    def notify_overdue_reports(
            *,
            dry_run: bool = False,
            batch_size: int = 5,
    ) -> dict[str, int]:
        """Email the reporter of every open report past its due date.

        Each report is notified at most once ever. The per-report conditional
        UPDATE sets overdue_notified_at only while it is still NULL, so
        overlapping runs, retries, and multiple workers cannot send the same
        notice twice. The same filter re-checks status and due_at at claim
        time, so a report resolved (or corrected) between the initial query
        and the claim is skipped.

        Only the reporter is emailed, and only when they still accept report
        notifications (Users.is_notified). A failed send releases the claim so
        the next daily run retries it.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")

        terminal_statuses = (
            HazardReports.Status.RESOLVED,
            HazardReports.Status.CLOSED,
            HazardReports.Status.INVALID,
        )

        def eligible_reports():
            return HazardReports.objects.filter(
                due_at__isnull=False,
                due_at__lte=timezone.now(),
                overdue_notified_at__isnull=True,
                reported_by__isnull=False,
                reported_by__is_notified=True,
            ).exclude(status__in=terminal_statuses)

        if dry_run:
            return {
                "notified": 0,
                "skipped": 0,
                "failed": 0,
                "would_notify": eligible_reports().count(),
            }

        notified = 0
        skipped = 0
        failed = 0
        last_id = 0

        while True:
            report_ids = list(
                eligible_reports()
                .filter(report_id__gt=last_id)
                .order_by("report_id")
                .values_list("report_id", flat=True)[:batch_size]
            )
            if not report_ids:
                break

            for report_id in report_ids:
                last_id = report_id

                claimed = eligible_reports().filter(report_id=report_id).update(
                    overdue_notified_at=timezone.now()
                )
                if not claimed:
                    skipped += 1
                    continue

                try:
                    report = (
                        HazardReports.objects.select_related("reported_by", "category")
                        .get(report_id=report_id)
                    )
                    sent = EmailService.send_report_overdue(
                        to_email=report.reported_by.email,
                        to_first_name=report.reported_by.first_name,
                        report_number=report.report_number,
                        category=report.category.hazard_name,
                        location=report.address,
                        submitted_at=ReportService._format_datetime(report.created_at),
                        due_at=ReportService._format_datetime(report.due_at),
                    )
                except Exception:
                    logger.exception(
                        "Failed to send overdue notice for report_id=%s", report_id
                    )
                    sent = False

                if not sent:
                    # Release the claim so the next daily run retries.
                    HazardReports.objects.filter(report_id=report_id).update(
                        overdue_notified_at=None
                    )
                    failed += 1
                    continue

                notified += 1

                try:
                    AuditLogService.log_report_activity(
                        actor=None,
                        report=report,
                        activity="OVERDUE_NOTIFIED",
                        description_override=(
                            f"REPORT {report.report_number} passed its target "
                            "resolution date and the reporter was notified by email."
                        ),
                    )
                except Exception:
                    # The email is already out; keep the claim rather than
                    # risking a duplicate on the next run.
                    logger.exception(
                        "Failed to log overdue notice for report_id=%s", report_id
                    )

        return {
            "notified": notified,
            "skipped": skipped,
            "failed": failed,
            "would_notify": 0,
        }

