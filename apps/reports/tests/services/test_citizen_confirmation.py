from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports.models import HazardReports
from apps.audits.models import AuditLogs
from apps.reports.services import ReportService
from apps.reports.exceptions.report_exception import ReportDoesNotExistException
from apps.reports.domain_errors.report_error import (
    ReportNotResolvedError,
    MandatoryRemarksStatusError,
)
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


def _resolved_report(reported_by, assigned_to=None):
    report = HazardReportFactory(
        status=HazardReports.Status.RESOLVED,
        reported_by=reported_by,
        assigned_to=assigned_to,
        resolved_at=timezone.now() - timedelta(days=1),
    )
    return report


@pytest.mark.django_db
class TestCitizenConfirmResolution:
    def test_reporter_closes_own_resolved_report(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(reported_by=citizen)

        result = ReportService.confirm_report_resolution(
            user=citizen,
            report_number=report.report_number,
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED
        assert report.confirmed_at is not None

    def test_confirmation_writes_audit_log(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(reported_by=citizen)

        ReportService.confirm_report_resolution(
            user=citizen,
            report_number=report.report_number,
        )

        status_logs = report.audit_logs.filter(
            action=AuditLogs.ActionType.STATUS_CHANGE
        )
        assert status_logs.count() == 1
        assert status_logs.first().user_id == citizen.user_id

    def test_confirmation_does_not_overwrite_remarks(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(reported_by=citizen)
        report.remarks = "Pothole patched and compacted."
        report.save(update_fields=["remarks"])

        ReportService.confirm_report_resolution(
            user=citizen,
            report_number=report.report_number,
        )

        report.refresh_from_db()
        assert report.remarks == "Pothole patched and compacted."

    def test_cannot_confirm_report_in_other_status(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.DISPATCHED,
            reported_by=citizen,
        )

        result = ReportService.confirm_report_resolution(
            user=citizen,
            report_number=report.report_number,
        )

        assert result.is_success is False
        assert result.error is ReportNotResolvedError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.DISPATCHED
        assert report.confirmed_at is None

    def test_cannot_confirm_someone_elses_report(self, citizen_role):
        reporter = UserFactory(role=citizen_role)
        other_citizen = UserFactory(role=citizen_role)
        report = _resolved_report(reported_by=reporter)

        with pytest.raises(ReportDoesNotExistException):
            ReportService.confirm_report_resolution(
                user=other_citizen,
                report_number=report.report_number,
            )

        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.confirmed_at is None

    def test_double_confirm_is_rejected(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(reported_by=citizen)

        ReportService.confirm_report_resolution(
            user=citizen,
            report_number=report.report_number,
        )
        result = ReportService.confirm_report_resolution(
            user=citizen,
            report_number=report.report_number,
        )

        assert result.is_success is False
        assert result.error is ReportNotResolvedError

    def test_resolved_report_is_not_auto_closed(self, citizen_role):
        # DO 47: unfinished/unconfirmed items are retained, never auto-closed.
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(reported_by=citizen)
        report.resolved_at = timezone.now() - timedelta(days=30)
        report.save(update_fields=["resolved_at"])

        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.confirmed_at is None


@pytest.mark.django_db
class TestStaffForceClose:
    def _officer_with_report(self, report_officer_role, citizen_role, status):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=status,
            assigned_to=officer,
            reported_by=UserFactory(role=citizen_role),
        )
        return officer, report

    def test_officer_force_closes_with_remarks(self, report_officer_role, citizen_role):
        officer, report = self._officer_with_report(
            report_officer_role, citizen_role, HazardReports.Status.ON_HOLD
        )

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.CLOSED,
            remarks="Not under DO 47 jurisdiction - referred to the barangay.",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED
        assert report.confirmed_at is None

    def test_officer_force_close_requires_remarks(self, report_officer_role, citizen_role):
        officer, report = self._officer_with_report(
            report_officer_role, citizen_role, HazardReports.Status.ON_HOLD
        )

        result = ReportService.update_authorized_assigned_report(
            user=officer,
            report_number=report.report_number,
            new_status_str=HazardReports.Status.CLOSED,
        )

        assert result.is_success is False
        assert result.error is MandatoryRemarksStatusError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.ON_HOLD


@pytest.mark.django_db
class TestConfirmResolutionEndpoint:
    def _url(self, report_number):
        return f"/reports/{report_number}/confirm-resolution/"

    def test_reporter_confirms_via_endpoint(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(reported_by=citizen)
        api_client.force_authenticate(user=citizen)

        response = api_client.post(self._url(report.report_number))

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED
        assert report.confirmed_at is not None

    def test_endpoint_conflicts_when_not_resolved(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.DISPATCHED,
            reported_by=citizen,
        )
        api_client.force_authenticate(user=citizen)

        response = api_client.post(self._url(report.report_number))

        assert response.status_code == 409
        assert response.data["error_code"] == "CONFIRMATION_NOT_RESOLVED"

    def test_staff_cannot_use_confirm_endpoint(self, api_client, report_officer_role, citizen_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            reported_by=UserFactory(role=citizen_role),
        )
        api_client.force_authenticate(user=officer)

        response = api_client.post(self._url(report.report_number))

        assert response.status_code == 403

    def test_citizen_cannot_patch_reports(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(reported_by=citizen)
        api_client.force_authenticate(user=citizen)

        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"status": "CLOSED", "remarks": "closing"},
            format="json",
        )

        assert response.status_code == 403
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
