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


def _overdue_report(reported_by, **kwargs):
    kwargs.setdefault("status", HazardReports.Status.IN_PROGRESS)
    kwargs.setdefault("due_at", timezone.now() - timedelta(days=1))
    return HazardReportFactory(reported_by=reported_by, **kwargs)


@pytest.mark.django_db
class TestNotifyOverdueReports:
    def test_notifies_reporter_of_open_overdue_report(self, citizen_role, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _overdue_report(citizen)

        result = ReportService.notify_overdue_reports()

        assert result["notified"] == 1
        email_mock.assert_called_once()
        kwargs = email_mock.call_args.kwargs
        assert kwargs["to_email"] == citizen.email
        assert kwargs["to_first_name"] == citizen.first_name
        assert kwargs["report_number"] == report.report_number
        assert kwargs["category"] == report.category.hazard_name
        assert kwargs["location"] == report.address
        assert kwargs["submitted_at"]
        assert kwargs["due_at"]

        report.refresh_from_db()
        assert report.overdue_notified_at is not None

    def test_notifies_only_once_ever(self, citizen_role, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        _overdue_report(citizen)

        first = ReportService.notify_overdue_reports()
        second = ReportService.notify_overdue_reports()

        assert first["notified"] == 1
        assert second["notified"] == 0
        assert second["skipped"] == 0
        email_mock.assert_called_once()

    def test_logs_an_audit_activity(self, citizen_role, mocker):
        mocker.patch("external.email.EmailService.send_report_overdue")
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _overdue_report(citizen)

        ReportService.notify_overdue_reports()

        log = report.audit_logs.get(action=AuditLogs.ActionType.ACTIVITY_NOTE)
        assert log.user_id is None
        assert log.payload["activity_note"]["type"] == "OVERDUE_NOTIFIED"
        assert "notified by email" in log.description

    def test_skips_report_not_yet_due(self, citizen_role, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = HazardReportFactory(
            status=HazardReports.Status.IN_PROGRESS,
            reported_by=citizen,
            due_at=timezone.now() + timedelta(days=2),
        )

        result = ReportService.notify_overdue_reports()

        assert result["notified"] == 0
        email_mock.assert_not_called()
        report.refresh_from_db()
        assert report.overdue_notified_at is None

    def test_skips_report_without_due_at(self, citizen_role, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        _overdue_report(citizen, due_at=None)

        result = ReportService.notify_overdue_reports()

        assert result["notified"] == 0
        email_mock.assert_not_called()

    @pytest.mark.parametrize(
        "status",
        [
            HazardReports.Status.RESOLVED,
            HazardReports.Status.CLOSED,
            HazardReports.Status.INVALID,
        ],
    )
    def test_skips_terminal_statuses(self, citizen_role, mocker, status):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _overdue_report(citizen, status=status)

        result = ReportService.notify_overdue_reports()

        assert result["notified"] == 0
        email_mock.assert_not_called()
        report.refresh_from_db()
        assert report.overdue_notified_at is None

    def test_skips_reporter_who_opted_out(self, citizen_role, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        citizen = UserFactory(role=citizen_role, is_notified=False)
        _overdue_report(citizen)

        result = ReportService.notify_overdue_reports()

        assert result["notified"] == 0
        email_mock.assert_not_called()

    def test_skips_report_without_reporter(self, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        _overdue_report(None)

        result = ReportService.notify_overdue_reports()

        assert result["notified"] == 0
        email_mock.assert_not_called()

    def test_dry_run_does_not_send_or_mark(self, citizen_role, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _overdue_report(citizen)

        result = ReportService.notify_overdue_reports(dry_run=True)

        assert result["notified"] == 0
        assert result["would_notify"] == 1
        email_mock.assert_not_called()
        report.refresh_from_db()
        assert report.overdue_notified_at is None

    def test_failed_send_releases_claim_for_retry(self, citizen_role, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue",
            return_value=False,
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _overdue_report(citizen)

        first = ReportService.notify_overdue_reports()

        assert first["notified"] == 0
        assert first["failed"] == 1
        report.refresh_from_db()
        assert report.overdue_notified_at is None

        email_mock.return_value = True
        second = ReportService.notify_overdue_reports()

        assert second["notified"] == 1
        report.refresh_from_db()
        assert report.overdue_notified_at is not None

    def test_management_command(self, citizen_role, mocker):
        mocker.patch("external.email.EmailService.send_report_overdue")
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _overdue_report(citizen)
        stdout = StringIO()

        call_command("notify_overdue_reports", stdout=stdout)

        report.refresh_from_db()
        assert report.overdue_notified_at is not None
        assert "Notified 1 overdue report(s)" in stdout.getvalue()

    def test_management_command_dry_run(self, citizen_role, mocker):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_overdue"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _overdue_report(citizen)
        stdout = StringIO()

        call_command("notify_overdue_reports", "--dry-run", stdout=stdout)

        email_mock.assert_not_called()
        report.refresh_from_db()
        assert report.overdue_notified_at is None
        assert "would be notified" in stdout.getvalue()
