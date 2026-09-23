import secrets
from typing import Any
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from django.db.models import Count, QuerySet, Q
from django.conf import settings

from apps.accounts.models import Users
from shared.results import DomainResult
from external.storage import StorageService, UploadIntent
from apps.reports.models import HazardReports, HazardCategories
from apps.reports.exceptions.report_exception import (
    InvalidImageCountException,
    InvalidHazardCategoryException,
    ReportDoesNotExistException,
    InvalidReportStatusException,
    InvalidReportSeverityException,
)
from apps.reports.domain_errors.report_error import (
    DuplicateStatusTransitionError,
    InvalidReportUpdateError,
    StatusResolutionImageConflictError,
    MandatoryRemarksStatusError,
    ResolutionImageRequiredError,
)
from apps.accounts.services import UserService
from apps.audits.services import AuditLogService
from apps.audits.models import AuditLogs
from shared.authorization.service import AuthorizationService
from shared.authorization import AllPermissions


class ReportService:
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
                user=None,
                old_status=old_status.label,
                new_status=report.status.label,
                report=report
            )

    @staticmethod
    def _get_next_report_assigned_to():
        active_statuses = [status for status in HazardReports.Status if status.phase < 4]

        assigned_active_reports = HazardReports.objects.filter(
            status__in=active_statuses,
            assigned_to__isnull=False,
        ).values('assigned_to').annotate(count=Count('report_id'))

        staff_to_active_report_map: dict[int, int] = {
            item['assigned_to']: item['count'] for item in assigned_active_reports
        }

        assigned_staff = UserService.get_next_staff_for_assignment(staff_to_active_report_map)
        return assigned_staff

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
    def get_status_list() -> DomainResult[list[dict[str, str]]]:
        return DomainResult.success(
            [
                {
                    "label": status.label,
                    "value": status.value,
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
    @transaction.atomic
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
        category = HazardCategories.objects.get_by_id_or_none(category_id)

        if not category:
            raise InvalidHazardCategoryException()

        ReportService._process_unassigned_reports()

        assigned_staff = ReportService._get_next_report_assigned_to()
        initial_status = HazardReports.Status.ASSIGNED if assigned_staff else HazardReports.Status.NEW

        report: HazardReports = HazardReports.objects.create(
            reported_by_id=reported_by_id,
            assigned_to=assigned_staff,
            category=category,
            latitude=latitude,
            longitude=longitude,
            address=address,
            description=description,
            status=initial_status,
            is_anonymous=is_anonymous
        )

        for image_url in image_urls:
            report.images.create(image_url=image_url)

        AuditLogService.log_create(
            user=report.reported_by,
            module=AuditLogs.ModuleType.REPORT,
            payload={
                "initial_status": report.status.label,
                "assigned_to": assigned_staff.email if assigned_staff else None,
            },
            target_object=report,
            target_identifier=report.report_number
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

        search_query = query_filters.get("q")
        if search_query:
            search_query = search_query.strip()

            queryset = queryset.filter(
                Q(report_number__icontains=search_query) |
                Q(category__hazard_name__icontains=search_query)
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
            "category"
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
            remarks: str|None=None,
            resolution_image_urls: list[str]|None=None
    ) -> DomainResult[None]:
        authorized_reports = ReportService._authorized_reports(user=user)

        report = authorized_reports.filter(report_number__iexact=report_number).first()
        if not report:
            raise ReportDoesNotExistException()

        updated_fields: list[str] = []

        new_status_str = new_status_str.strip().upper() if new_status_str else None
        new_severity_str = new_severity_str.strip().upper() if new_severity_str else None
        remarks = remarks.strip() if remarks else None

        if (remarks and not new_status_str) or (resolution_image_urls and not new_status_str):
            return DomainResult.error(InvalidReportUpdateError)

        if new_status_str:
            if new_status_str not in HazardReports.Status:
                raise InvalidReportStatusException()

            if new_status_str == report.status:
                return DomainResult.error(DuplicateStatusTransitionError)

            if new_status_str in HazardReports.Status.get_mandatory_remarks_statuses() and not remarks:
                return DomainResult.error(MandatoryRemarksStatusError)

            old_status = HazardReports.Status(report.status)
            report.status = HazardReports.Status(new_status_str)
            updated_fields.append("status")

            report.remarks = remarks
            updated_fields.append("remarks")

            if new_status_str == HazardReports.Status.RESOLVED:
                if not resolution_image_urls:
                    return DomainResult.error(ResolutionImageRequiredError)

                report.resolved_at = timezone.now()
                updated_fields.append("resolved_at")

                for resolution_image_url in resolution_image_urls:
                    report.images.create(
                        image_url=resolution_image_url,
                        is_resolution=True
                    )
            else:
                if resolution_image_urls:
                    return DomainResult.error(StatusResolutionImageConflictError)

            AuditLogService.log_report_status_change(
                user=user,
                old_status=old_status.label,
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
                user=user,
                old_severity=old_severity,
                new_severity=report.severity,
                report=report
            )

        if updated_fields:
            report.save(update_fields=updated_fields)

        return DomainResult.success(None)

