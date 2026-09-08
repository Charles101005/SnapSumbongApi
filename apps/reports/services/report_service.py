import secrets
import string
from typing import Any
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from django.db.models import Count, QuerySet
from django.conf import settings

from shared.results import DomainResult
from external.storage import StorageService, UploadIntent
from apps.reports.models import HazardReports, HazardCategories
from apps.reports.exceptions.report_exception import InvalidImageCountException, InvalidHazardCategoryException
from apps.accounts.services import UserService


class ReportService:
    @staticmethod
    def _generate_report_number() -> str:
        # REPT-YYYYMMDD-6RandomBase36Chars

        PREFIX = "REPT"
        SUFFIX_LENGTH = 6
        SUFFIX_CHOICES = string.digits + string.ascii_uppercase

        date_str = timezone.now().strftime("%Y%m%d")
        suffix_str = ''.join(secrets.choice(SUFFIX_CHOICES) for _ in range(SUFFIX_LENGTH))

        return f"{PREFIX}-{date_str}-{suffix_str}"

    @staticmethod
    def _process_unassigned_reports() -> None:
        unassigned_active_reports: QuerySet[HazardReports] = HazardReports.objects.filter(
            status=HazardReports.Status.NEW,
            assigned_to__isnull=True,
        ).order_by('created_at').select_for_update(skip_locked=True)[:5]

        if not unassigned_active_reports.exists():
            return

        for report in unassigned_active_reports:
            assigned_staff = ReportService._get_next_report_assigned_to()

            if not assigned_staff:
                return

            report.assigned_to = assigned_staff
            report.status = HazardReports.Status.OPEN
            report.save(update_fields=[
                'assigned_to',
                'status',
            ])

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
    def get_hazard_image_upload_credentials(image_count: int) -> DomainResult[dict[str, Any]]:
        if image_count <= 0 or image_count > settings.STORAGE_CONFIG["MAX_SIGNATURE_COUNT"]:
            raise InvalidImageCountException()

        now = timezone.now()
        folder_path = f"hazard_reports/{now.strftime('%Y')}/{now.strftime('%m')}"

        batch_id = secrets.token_urlsafe(16)
        file_names = [f"{batch_id}_img{i}" for i in range(1, image_count + 1)]

        upload_credentials = StorageService.get_upload_credentials(
            folder_path=folder_path,
            file_names=file_names,
            intent=UploadIntent.HAZARD_REPORT
        )

        return DomainResult.success(upload_credentials)

    @staticmethod
    @transaction.atomic
    def create_assign_hazard_report(
            *,
            reported_by_id: int,
            category_ids: list[int],
            latitude: Decimal,
            longitude: Decimal,
            address: str,
            description: str,
            is_anonymous: bool,
            image_urls: list[str],
    ) -> DomainResult[HazardReports]:
        categories = HazardCategories.objects.get_by_ids_or_none(category_ids)

        if not categories:
            raise InvalidHazardCategoryException()

        ReportService._process_unassigned_reports()

        assigned_staff = ReportService._get_next_report_assigned_to()
        initial_status = HazardReports.Status.OPEN if assigned_staff else HazardReports.Status.NEW

        report: HazardReports = HazardReports.objects.create(
            report_number=ReportService._generate_report_number(),
            reported_by_id=reported_by_id,
            assigned_to=assigned_staff,
            latitude=latitude,
            longitude=longitude,
            address=address,
            description=description,
            status=initial_status,
            is_anonymous=is_anonymous
        )

        report.categories.set(categories)

        for image_url in image_urls:
            report.images.create(image_url=image_url)

        return DomainResult.success(report)
