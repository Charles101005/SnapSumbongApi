from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.domain_errors.report_error import (
    AssignedStatusTransitionError,
    MandatorySeverityStatusError,
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
class TestAssignedOnlyMovesToUnderReview:
    def test_assigned_to_under_review_without_severity_succeeds(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.ASSIGNED)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.UNDER_REVIEW,
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
        assert report.severity is None

    def test_assigned_to_under_review_with_severity_in_same_update(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.ASSIGNED)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.UNDER_REVIEW,
            new_severity_str="P2",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
        assert report.severity == "P2"

    def test_assigned_cannot_skip_to_dispatched(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.ASSIGNED)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.DISPATCHED,
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
class TestSeverityRequiredToLeaveUnderReview:
    def test_dispatch_without_severity_is_rejected(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.UNDER_REVIEW)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.DISPATCHED,
        )

        assert result.is_success is False
        assert result.error is MandatorySeverityStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
        assert report.severity is None

    def test_on_hold_without_severity_is_rejected(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.UNDER_REVIEW)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.ON_HOLD,
            remarks="Referred to the city engineering office.",
        )

        assert result.is_success is False
        assert result.error is MandatorySeverityStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW

    def test_severity_in_same_update_allows_dispatch(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.UNDER_REVIEW)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.DISPATCHED,
            new_severity_str="P2",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.DISPATCHED
        assert report.severity == "P2"

    def test_existing_severity_allows_status_only_transition(self, report_officer_role):
        officer, report = _setup_report(
            report_officer_role, HazardReports.Status.UNDER_REVIEW, severity="P3"
        )

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.DISPATCHED,
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.DISPATCHED
        assert report.severity == "P3"

    def test_severity_can_be_set_without_leaving_under_review(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.UNDER_REVIEW)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_severity_str="P4",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
        assert report.severity == "P4"

    def test_invalid_flag_does_not_require_severity(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.UNDER_REVIEW)

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
        officer, report = _setup_report(report_officer_role, HazardReports.Status.UNDER_REVIEW)

        with pytest.raises(InvalidReportSeverityException):
            ReportService.update_authorized_assigned_report(
                user=officer,
                report_number=report.report_number,
                new_status_str=HazardReports.Status.DISPATCHED,
                new_severity_str="P9",
            )

        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
        assert report.severity is None

    def test_blank_severity_string_is_treated_as_missing(self, report_officer_role):
        officer, report = _setup_report(report_officer_role, HazardReports.Status.UNDER_REVIEW)

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.DISPATCHED,
            new_severity_str="   ",
        )

        assert result.is_success is False
        assert result.error is MandatorySeverityStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.UNDER_REVIEW
