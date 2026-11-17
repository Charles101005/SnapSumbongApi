from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audits.models import AuditLogs
from apps.reports.domain_errors.report_error import (
    ReportNotReopenableError,
    ReopenRemarksRequiredError,
)
from apps.reports.exceptions.report_exception import ReportDoesNotExistException
from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


REOPEN_REASON = "The pothole is still there and the repair has not held up."


def _report(reported_by, *, status=HazardReports.Status.RESOLVED, **kwargs):
    defaults = {
        "reported_by": reported_by,
        "status": status,
        "resolved_at": timezone.now() - timedelta(days=1),
        "validated_by_name": "Engr. Dela Cruz",
    }
    defaults.update(kwargs)
    return HazardReportFactory(**defaults)


@pytest.mark.django_db
class TestCitizenReopen:
    def test_reporter_reopens_resolved_report(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen)

        result = ReportService.reopen_report_by_reporter(
            user=citizen,
            report_number=report.report_number,
            remarks=REOPEN_REASON,
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS
        assert report.resolved_at is None
        assert report.confirmed_at is None
        assert report.auto_closed_at is None
        assert report.validated_by is None
        assert report.validated_by_name is None
        assert report.remarks == REOPEN_REASON

        log = report.audit_logs.get(action=AuditLogs.ActionType.STATUS_CHANGE)
        assert log.user_id == citizen.user_id
        assert log.payload["status_change"] == {
            "from": "Resolved",
            "to": "In Progress",
        }
        assert log.payload["remarks"] == REOPEN_REASON
        assert "reopened" in log.description

    def test_cannot_reopen_citizen_confirmed_closed_report(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(
            citizen,
            status=HazardReports.Status.CLOSED,
            confirmed_at=timezone.now(),
        )

        result = ReportService.reopen_report_by_reporter(
            user=citizen,
            report_number=report.report_number,
            remarks=REOPEN_REASON,
        )

        assert result.is_success is False
        assert result.error is ReportNotReopenableError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED
        assert report.confirmed_at is not None

    def test_cannot_reopen_auto_closed_report(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(
            citizen,
            status=HazardReports.Status.CLOSED,
            auto_closed_at=timezone.now(),
        )

        result = ReportService.reopen_report_by_reporter(
            user=citizen,
            report_number=report.report_number,
            remarks=REOPEN_REASON,
        )

        assert result.is_success is False
        assert result.error is ReportNotReopenableError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED
        assert report.auto_closed_at is not None

    def test_reopen_requires_a_long_enough_reason(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen)

        result = ReportService.reopen_report_by_reporter(
            user=citizen,
            report_number=report.report_number,
            remarks="Broken",
        )

        assert result.is_success is False
        assert result.error is ReopenRemarksRequiredError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED

    def test_reopen_requires_a_reason(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen)

        result = ReportService.reopen_report_by_reporter(
            user=citizen,
            report_number=report.report_number,
            remarks="   ",
        )

        assert result.is_success is False
        assert result.error is ReopenRemarksRequiredError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED

    def test_cannot_reopen_an_in_progress_report(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen, status=HazardReports.Status.IN_PROGRESS)

        result = ReportService.reopen_report_by_reporter(
            user=citizen,
            report_number=report.report_number,
            remarks=REOPEN_REASON,
        )

        assert result.is_success is False
        assert result.error is ReportNotReopenableError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_cannot_reopen_an_invalid_report(self, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen, status=HazardReports.Status.INVALID)

        result = ReportService.reopen_report_by_reporter(
            user=citizen,
            report_number=report.report_number,
            remarks=REOPEN_REASON,
        )

        assert result.is_success is False
        assert result.error is ReportNotReopenableError
        report.refresh_from_db()
        assert report.status == HazardReports.Status.INVALID

    def test_cannot_reopen_someone_elses_report(self, citizen_role):
        reporter = UserFactory(role=citizen_role)
        other_citizen = UserFactory(role=citizen_role)
        report = _report(reporter)

        with pytest.raises(ReportDoesNotExistException):
            ReportService.reopen_report_by_reporter(
                user=other_citizen,
                report_number=report.report_number,
                remarks=REOPEN_REASON,
            )

    def test_reopen_sends_status_update_email(
        self, citizen_role, mocker, django_capture_on_commit_callbacks
    ):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_status_update"
        )
        citizen = UserFactory(role=citizen_role, is_notified=True)
        report = _report(citizen)

        with django_capture_on_commit_callbacks(execute=True):
            ReportService.reopen_report_by_reporter(
                user=citizen,
                report_number=report.report_number,
                remarks=REOPEN_REASON,
            )

        email_mock.assert_called_once()
        kwargs = email_mock.call_args.kwargs
        assert kwargs["to_email"] == citizen.email
        assert kwargs["report_number"] == report.report_number
        assert kwargs["remarks"] == REOPEN_REASON


@pytest.mark.django_db
class TestCitizenReopenEndpoint:
    def _url(self, report_number):
        return f"/reports/{report_number}/reopen/"

    def test_reporter_reopens_via_endpoint(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen)
        api_client.force_authenticate(user=citizen)

        response = api_client.post(
            self._url(report.report_number),
            {"remarks": REOPEN_REASON},
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == HazardReports.Status.IN_PROGRESS

    def test_endpoint_requires_a_long_enough_reason(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen)
        api_client.force_authenticate(user=citizen)

        response = api_client.post(
            self._url(report.report_number),
            {"remarks": "Too short"},
            format="json",
        )

        assert response.status_code == 400
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED

    def test_endpoint_rejects_other_citizen(self, api_client, citizen_role):
        reporter = UserFactory(role=citizen_role)
        other_citizen = UserFactory(role=citizen_role)
        report = _report(reporter)
        api_client.force_authenticate(user=other_citizen)

        response = api_client.post(
            self._url(report.report_number),
            {"remarks": REOPEN_REASON},
            format="json",
        )

        assert response.status_code == 400
        report.refresh_from_db()
        assert report.status == HazardReports.Status.RESOLVED

    def test_staff_cannot_use_endpoint(self, api_client, report_officer_role, citizen_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = _report(UserFactory(role=citizen_role))
        api_client.force_authenticate(user=officer)

        response = api_client.post(
            self._url(report.report_number),
            {"remarks": REOPEN_REASON},
            format="json",
        )

        assert response.status_code == 403

    def test_citizen_timeline_includes_the_reopen_entry(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen)
        ReportService.reopen_report_by_reporter(
            user=citizen,
            report_number=report.report_number,
            remarks=REOPEN_REASON,
        )
        api_client.force_authenticate(user=citizen)

        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        reopen = next(
            entry for entry in response.data["status_timeline"]
            if entry["action"] == "STATUS_CHANGE"
            and entry["from_status"] == "Resolved"
            and entry["to_status"] == "In Progress"
        )
        assert reopen["remarks"] == REOPEN_REASON

    def test_endpoint_rejects_non_reopenable_status(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(citizen, status=HazardReports.Status.IN_PROGRESS)
        api_client.force_authenticate(user=citizen)

        response = api_client.post(
            self._url(report.report_number),
            {"remarks": REOPEN_REASON},
            format="json",
        )

        assert response.status_code == 409
        assert response.data["error_code"] == "REPORT_NOT_REOPENABLE"

    def test_endpoint_rejects_closed_report(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = _report(
            citizen,
            status=HazardReports.Status.CLOSED,
            confirmed_at=timezone.now(),
        )
        api_client.force_authenticate(user=citizen)

        response = api_client.post(
            self._url(report.report_number),
            {"remarks": REOPEN_REASON},
            format="json",
        )

        assert response.status_code == 409
        assert response.data["error_code"] == "REPORT_NOT_REOPENABLE"
        report.refresh_from_db()
        assert report.status == HazardReports.Status.CLOSED
