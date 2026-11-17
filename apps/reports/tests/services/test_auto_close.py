from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


AUTO_CLOSE_REASON = (
    "Automatically closed after 7 days without reporter confirmation."
)


def _resolved_report(reported_by, *, days_ago=8, **kwargs):
    return HazardReportFactory(
        status=HazardReports.Status.RESOLVED,
        reported_by=reported_by,
        resolved_at=timezone.now() - timedelta(days=days_ago),
        **kwargs,
    )


@pytest.mark.django_db
class TestAutoCloseResolvedReports:
    def test_closes_report_after_seven_days(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=8)

        result = ReportService.auto_close_resolved_reports()

        assert result["closed"] == 1
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED
        assert report.auto_closed_at is not None
        assert report.confirmed_at is None
        assert report.resolved_at is not None

        log = report.audit_logs.get(action=AuditLogs.ActionType.STATUS_CHANGE)
        assert log.user_id is None
        assert log.payload["status_change"] == {
            "from": "Resolved",
            "to": "Closed",
        }
        assert log.payload["remarks"] == AUTO_CLOSE_REASON
        assert "automatically closed by the System" in log.description

    def test_does_not_close_before_seven_days(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=6)

        result = ReportService.auto_close_resolved_reports()

        assert result["closed"] == 0
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.auto_closed_at is None

    def test_exactly_seven_days_is_closed(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=7)

        result = ReportService.auto_close_resolved_reports()

        assert result["closed"] == 1
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED

    def test_skips_resolved_report_without_resolved_at(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.RESOLVED,
            reported_by=citizen,
            resolved_at=None,
        )

        result = ReportService.auto_close_resolved_reports()

        assert result["closed"] == 0
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED

    def test_skips_non_resolved_reports(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.IN_PROGRESS,
            reported_by=citizen,
            resolved_at=timezone.now() - timedelta(days=30),
        )

        result = ReportService.auto_close_resolved_reports()

        assert result["closed"] == 0
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_skips_confirmed_resolved_report(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(
            citizen,
            days_ago=30,
            confirmed_at=timezone.now(),
        )

        result = ReportService.auto_close_resolved_reports()

        assert result["closed"] == 0
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.auto_closed_at is None

    def test_dry_run_does_not_change_reports(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=8)

        result = ReportService.auto_close_resolved_reports(dry_run=True)

        assert result["closed"] == 0
        assert result["would_close"] == 1
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert report.auto_closed_at is None

    def test_is_idempotent(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=8)

        first = ReportService.auto_close_resolved_reports()
        second = ReportService.auto_close_resolved_reports()

        assert first["closed"] == 1
        assert second["closed"] == 0
        assert report.audit_logs.filter(
            action=AuditLogs.ActionType.STATUS_CHANGE
        ).count() == 1

    def test_days_override(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=3)

        assert ReportService.auto_close_resolved_reports()["closed"] == 0
        assert ReportService.auto_close_resolved_reports(
            older_than_days=2
        )["closed"] == 1
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED

    def test_sends_status_update_email(
        self, citizen_role, mocker, django_capture_on_commit_callbacks
    ):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_status_update"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _resolved_report(citizen, days_ago=8)

        with django_capture_on_commit_callbacks(execute=True):
            ReportService.auto_close_resolved_reports()

        email_mock.assert_called_once()
        kwargs = email_mock.call_args.kwargs
        assert kwargs["to_email"] == citizen.email
        assert kwargs["report_number"] == report.report_number
        assert "Automatically closed" in kwargs["remarks"]

    def test_management_command_closes_reports(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=8)
        stdout = StringIO()

        call_command("auto_close_resolved_reports", stdout=stdout)

        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED
        assert "Auto-closed 1 resolved report(s)" in stdout.getvalue()

    def test_management_command_dry_run(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=8)
        stdout = StringIO()

        call_command("auto_close_resolved_reports", "--dry-run", stdout=stdout)

        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED
        assert "would be auto-closed" in stdout.getvalue()


@pytest.mark.django_db
class TestAutoCloseExposure:
    def test_citizen_detail_exposes_auto_closed_at(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _resolved_report(citizen, days_ago=8)

        ReportService.auto_close_resolved_reports()

        api_client.force_authenticate(user=citizen)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert response.data["auto_closed_at"] is not None
        assert response.data["confirmed_at"] is None
