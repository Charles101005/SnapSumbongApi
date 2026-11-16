from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.domain_errors.report_error import (
    AssignedStatusTransitionError,
    MandatoryRemarksStatusError,
    MandatorySeverityStatusError,
    StatusTransitionNotAllowedError,
)
from apps.reports.exceptions.report_exception import InvalidReportSeverityException
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


def _setup_report(report_officer_role, status, severity=None):
    officer = UserFactory(role=report_officer_role, is_staff=True)
    report = HazardReportFactory(
        status=status,
        severity=severity,
        due_at=timezone.now() + timedelta(days=2),
    )
    report.assigned_to = officer
    report.save(update_fields=["assigned_to"])
    return officer, report


@pytest.mark.django_db
class TestAssignedOnlyMovesToInProgress:
    def test_assigned_to_in_progress_without_severity_is_rejected(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.ASSIGNED)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.IN_PROGRESS,
        )

        assert result.is_success is False
        assert result.error is MandatorySeverityStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ASSIGNED
        assert report.severity is None

    def test_assigned_to_in_progress_with_severity_in_same_update(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.ASSIGNED)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.IN_PROGRESS,
            new_severity_str="P2",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS
        assert report.severity == "P2"

    def test_assigned_cannot_skip_to_resolved(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.ASSIGNED)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            new_severity_str="P2",
            remarks="Done.",
            resolution_images=[
                {"image_url": "https://res.cloudinary.com/demo/during.jpg", "photo_type": "DURING"},
                {"image_url": "https://res.cloudinary.com/demo/after.jpg", "photo_type": "AFTER"},
            ],
            validated_by_name="Engr. Dela Cruz",
        )

        assert result.is_success is False
        assert result.error is AssignedStatusTransitionError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ASSIGNED

    def test_assigned_cannot_skip_to_invalid(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.ASSIGNED)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.INVALID,
            remarks="Duplicate of an existing report.",
        )

        assert result.is_success is False
        assert result.error is AssignedStatusTransitionError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ASSIGNED


@pytest.mark.django_db
class TestSeverityRequiredDuringHandling:
    def test_on_hold_without_severity_is_rejected(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.IN_PROGRESS)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.ON_HOLD,
            remarks="Referred to the city engineering office.",
        )

        assert result.is_success is False
        assert result.error is MandatorySeverityStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_resolved_without_severity_is_rejected(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.IN_PROGRESS)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            remarks="Done.",
            resolution_images=[
                {"image_url": "https://res.cloudinary.com/demo/during.jpg", "photo_type": "DURING"},
                {"image_url": "https://res.cloudinary.com/demo/after.jpg", "photo_type": "AFTER"},
            ],
            validated_by_name="Engr. Dela Cruz",
        )

        assert result.is_success is False
        assert result.error is MandatorySeverityStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_severity_in_same_update_allows_on_hold(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.IN_PROGRESS)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.ON_HOLD,
            new_severity_str="P2",
            remarks="Awaiting external agency confirmation.",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ON_HOLD
        assert report.severity == "P2"

    def test_existing_severity_allows_status_only_transition(self, report_officer_role):
        officer, report = _setup_report(
            report_officer_role, HazardReports.Status.IN_PROGRESS, severity="P3"
        )

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.ON_HOLD,
            remarks="Awaiting external agency confirmation.",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ON_HOLD
        assert report.severity == "P3"

    def test_severity_can_be_set_without_changing_status(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.IN_PROGRESS)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_severity_str="P4",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS
        assert report.severity == "P4"

    def test_invalid_flag_does_not_require_severity(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.IN_PROGRESS)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.INVALID,
            remarks="Duplicate of an existing report.",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.INVALID
        assert report.severity is None

    def test_invalid_severity_value_rejected_with_rollback(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.IN_PROGRESS)

        with pytest.raises(InvalidReportSeverityException):
            ReportService.update_authorized_assigned_report(
                user=officer,
                report_number=report.report_number,
                new_status_str=HazardReports.Status.ON_HOLD,
                new_severity_str="P9",
                remarks="Awaiting external agency confirmation.",
            )

        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS
        assert report.severity is None

    def test_blank_severity_string_is_treated_as_missing(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.IN_PROGRESS)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.ON_HOLD,
            new_severity_str="   ",
            remarks="Awaiting external agency confirmation.",
        )

        assert result.is_success is False
        assert result.error is MandatorySeverityStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS


@pytest.mark.django_db
class TestResolvedRequiresRemarks:
    def test_resolved_without_remarks_is_rejected(self, report_officer_role):
        officer, report = _setup_report(
            report_officer_role, HazardReports.Status.IN_PROGRESS, severity="P2"
        )

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            resolution_images=[
                {"image_url": "https://res.cloudinary.com/demo/during.jpg", "photo_type": "DURING"},
                {"image_url": "https://res.cloudinary.com/demo/after.jpg", "photo_type": "AFTER"},
            ],
            validated_by_name="Engr. Dela Cruz",
        )

        assert result.is_success is False
        assert result.error is MandatoryRemarksStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_resolved_with_blank_remarks_is_rejected(self, report_officer_role):
        officer, report = _setup_report(
            report_officer_role, HazardReports.Status.IN_PROGRESS, severity="P2"
        )

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.RESOLVED,
            remarks="   ",
            resolution_images=[
                {"image_url": "https://res.cloudinary.com/demo/during.jpg", "photo_type": "DURING"},
                {"image_url": "https://res.cloudinary.com/demo/after.jpg", "photo_type": "AFTER"},
            ],
            validated_by_name="Engr. Dela Cruz",
        )

        assert result.is_success is False
        assert result.error is MandatoryRemarksStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS


@pytest.mark.django_db
class TestTransitionMatrixEnforcement:
    def test_manual_new_to_assigned_assigns_the_actor(self, supervisor_role):
        officer = UserFactory(role=supervisor_role, is_staff=True)
        report = HazardReportFactory(
            status=HazardReports.Status.NEW,
            due_at=timezone.now() + timedelta(days=2),
        )

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.ASSIGNED,
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ASSIGNED
        assert report.assigned_to_id == officer.user_id

    def test_in_progress_cannot_jump_to_closed(self, report_officer_role):
        officer, report = _setup_report(
            report_officer_role, HazardReports.Status.IN_PROGRESS, severity="P2"
        )

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.CLOSED,
            remarks="Out of jurisdiction.",
        )

        assert result.is_success is False
        assert result.error is StatusTransitionNotAllowedError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS
