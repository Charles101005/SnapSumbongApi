from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports, ReportImages
from apps.reports.services import ReportService
from apps.reports.domain_errors.report_error import (
    ResolutionImageRequiredError,
    MissingDuringPhotoError,
    MissingAfterPhotoError,
    StatusResolutionImageConflictError,
)
from apps.reports.tests.factories import HazardCategoryFactory, HazardReportFactory
from apps.accounts.tests.factories import UserFactory


def _resolve_images(during_url="https://res.cloudinary.com/demo/during.jpg",
                    after_url="https://res.cloudinary.com/demo/after.jpg"):
    images = []
    if during_url:
        images.append({"image_url": during_url, "photo_type": ReportImages.PhotoType.DURING})
    if after_url:
        images.append({"image_url": after_url, "photo_type": ReportImages.PhotoType.AFTER})
    return images


@pytest.mark.django_db
class TestCreateReportPhotoType:
    def test_citizen_submission_images_are_tagged_before(self, citizen_role):
        citizen = UserFactory(role=citizen_role)

        result = ReportService.create_assign_hazard_report(
            reported_by_id=citizen.user_id,
            category_id=HazardCategoryFactory().hazard_id,
            latitude=Decimal("14.599500"),
            longitude=Decimal("120.984200"),
            address="Sampaloc, Manila, Metro Manila",
            description="Deep pothole in the middle of the road",
            is_anonymous=False,
            image_urls=[
                "https://res.cloudinary.com/demo/before1.jpg",
                "https://res.cloudinary.com/demo/before2.jpg",
            ],
        )

        report = result.value
        photo_types = list(report.images.values_list("photo_type", flat=True))
        assert photo_types == [
            ReportImages.PhotoType.BEFORE,
            ReportImages.PhotoType.BEFORE,
        ]


@pytest.mark.django_db
class TestResolvePhotologRules:
    def _officer_with_report(self, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=HazardReports.Status.DISPATCHED,
            assigned_to=officer,
            due_at=timezone.now() + timedelta(days=2),
        )
        return officer, report

    def test_resolve_with_during_and_after_succeeds(self, report_officer_role):
        officer, report = self._officer_with_report(report_officer_role)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            remarks="Pothole patched and compacted.",
            resolution_images=_resolve_images(),
            validated_by_name="Engr. Dela Cruz",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.resolved_at is not None
        assert report.validated_by_id == officer.user_id
        assert report.validated_by_name == "Engr. Dela Cruz"

        resolution_types = set(
            report.images.exclude(photo_type=ReportImages.PhotoType.BEFORE)
            .values_list("photo_type", flat=True)
        )
        assert resolution_types == {ReportImages.PhotoType.DURING, ReportImages.PhotoType.AFTER}

    def test_resolve_without_images_is_rejected(self, report_officer_role):
        officer, report = self._officer_with_report(report_officer_role)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            remarks="Done.",
            resolution_images=None,
        )

        assert result.is_success is False
        assert result.error is ResolutionImageRequiredError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.DISPATCHED

    def test_resolve_missing_during_photo_is_rejected(self, report_officer_role):
        officer, report = self._officer_with_report(report_officer_role)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            remarks="Done.",
            resolution_images=_resolve_images(during_url=None),
        )

        assert result.is_success is False
        assert result.error is MissingDuringPhotoError
        report.refresh_from_db()
        assert report.resolved_at is None

    def test_resolve_missing_after_photo_is_rejected(self, report_officer_role):
        officer, report = self._officer_with_report(report_officer_role)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            remarks="Done.",
            resolution_images=_resolve_images(after_url=None),
        )

        assert result.is_success is False
        assert result.error is MissingAfterPhotoError
        report.refresh_from_db()
        assert report.resolved_at is None

    def test_resolution_images_on_non_resolved_status_are_rejected(self, report_officer_role):
        officer, report = self._officer_with_report(report_officer_role)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.CLOSED,
            remarks="Out of jurisdiction.",
            resolution_images=_resolve_images(),
        )

        assert result.is_success is False
        assert result.error is StatusResolutionImageConflictError

    def test_partial_during_only_images_rejected_even_if_multiple(self, report_officer_role):
        officer, report = self._officer_with_report(report_officer_role)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            remarks="Done.",
            resolution_images=[
                {"image_url": "https://res.cloudinary.com/demo/d1.jpg", "photo_type": ReportImages.PhotoType.DURING},
                {"image_url": "https://res.cloudinary.com/demo/d2.jpg", "photo_type": ReportImages.PhotoType.DURING},
            ],
        )

        assert result.is_success is False
        assert result.error is MissingAfterPhotoError
