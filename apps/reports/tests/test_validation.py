from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.domain_errors.report_error import SelfValidationDeniedError
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


def _resolve_images():
    return [
        {"image_url": "https://res.cloudinary.com/demo/during.jpg", "photo_type": "DURING"},
        {"image_url": "https://res.cloudinary.com/demo/after.jpg", "photo_type": "AFTER"},
    ]


def _resolve(user, report, remarks="Pothole patched and compacted."):
    return ReportService.update_authorized_assigned_report(
        user=user,
        report_number=report.report_number,
        new_status_str=HazardReports.Status.RESOLVED,
        remarks=remarks,
        resolution_images=_resolve_images(),
    )


@pytest.mark.django_db
class TestIndependentValidation:
    def _assigned_report(self):
        return HazardReportFactory(
            status=HazardReports.Status.DISPATCHED,
            due_at=timezone.now() + timedelta(days=2),
        )

    def test_assignee_cannot_validate_own_resolution(self, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = officer
        report.save(update_fields=["assigned_to"])

        result = _resolve(officer, report)

        assert result.is_success is False
        assert result.error is SelfValidationDeniedError

        report.refresh_from_db()
        assert report.status == HazardReports.Status.DISPATCHED
        assert report.resolved_at is None
        assert report.validated_by is None

    def test_different_staff_member_can_validate(self, report_officer_role, supervisor_role):
        assignee = UserFactory(role=report_officer_role, is_staff=True)
        validator = UserFactory(role=supervisor_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = assignee
        report.save(update_fields=["assigned_to"])

        result = _resolve(validator, report)

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.validated_by_id == validator.user_id
        assert report.validated_by_id != report.assigned_to_id

    @override_settings(ALLOW_SELF_VALIDATION=True)
    def test_self_validation_allowed_by_demo_flag(self, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = officer
        report.save(update_fields=["assigned_to"])

        result = _resolve(officer, report)

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.validated_by_id == officer.user_id

    def test_unassigned_report_can_be_resolved_by_anyone(self, supervisor_role):
        # Supervisor holds REPORTS.READ_ALL, so unassigned reports are in
        # scope; a Report Officer would only see their own assignments.
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        report = self._assigned_report()
        assert report.assigned_to_id is None

        result = _resolve(supervisor, report)

        assert result.is_success
        report.refresh_from_db()
        assert report.validated_by_id == supervisor.user_id

    def test_denied_validation_does_not_record_validator(self, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._assigned_report()
        report.assigned_to = officer
        report.save(update_fields=["assigned_to"])

        _resolve(officer, report)

        report.refresh_from_db()
        assert report.validated_by_id is None
