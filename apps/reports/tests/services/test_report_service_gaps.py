from decimal import Decimal

import pytest
from django.conf import settings

from apps.accounts.tests.factories import UserFactory
from apps.audits.models import AuditLogs
from apps.reports.exceptions.report_exception import InvalidImageCountException
from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.tests.factories import HazardCategoryFactory, HazardReportFactory


@pytest.mark.django_db
class TestHazardImageUploadCredentialsValidation:
    def test_zero_image_count_is_rejected(self, citizen_role):
        user = UserFactory(role=citizen_role)

        with pytest.raises(InvalidImageCountException):
            ReportService.get_hazard_image_upload_credentials(
                user=user, image_count=0
            )

    def test_image_count_above_the_max_is_rejected(self, citizen_role):
        user = UserFactory(role=citizen_role)

        with pytest.raises(InvalidImageCountException):
            ReportService.get_hazard_image_upload_credentials(
                user=user,
                image_count=settings.STORAGE_CONFIG["MAX_SIGNATURE_COUNT"] + 1,
            )


@pytest.mark.django_db
class TestUnassignedReportProcessing:
    """Creating any report triggers the sweep that auto-assigns pending
    NEW reports (the automated first-assignment path)."""

    @staticmethod
    def _create_report(citizen):
        return ReportService.create_assign_hazard_report(
            reported_by_id=citizen.user_id,
            category_id=HazardCategoryFactory().hazard_id,
            latitude=Decimal("14.599500"),
            longitude=Decimal("120.984200"),
            address="Sampaloc, Manila, Metro Manila",
            description="Submission triggers the assignment sweep.",
            is_anonymous=False,
            image_urls=["https://res.cloudinary.com/demo/submit.jpg"],
        ).value

    def test_pending_report_is_assigned_to_free_staff(
        self, report_officer_role
    ):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        citizen = UserFactory()
        pending = HazardReportFactory(
            status=HazardReports.Status.NEW, assigned_to=None
        )

        self._create_report(citizen)

        pending.refresh_from_db()
        assert pending.assigned_to_id == officer.user_id
        assert pending.status == HazardReports.Status.ASSIGNED

        status_logs = AuditLogs.objects.filter(
            action=AuditLogs.ActionType.STATUS_CHANGE
        )
        assert status_logs.count() == 1
        log = status_logs.get()
        assert log.user_id is None
        assert "by the System" in log.description

    def test_sweep_returns_early_when_no_staff_is_available(self):
        citizen = UserFactory()
        pending = HazardReportFactory(
            status=HazardReports.Status.NEW, assigned_to=None
        )

        report = self._create_report(citizen)

        pending.refresh_from_db()
        assert pending.assigned_to_id is None
        assert pending.status == HazardReports.Status.NEW
        assert report.assigned_to is None
        assert not AuditLogs.objects.filter(
            action=AuditLogs.ActionType.STATUS_CHANGE
        ).exists()


@pytest.mark.django_db
class TestStatusUpdateEmailDispatch:
    def test_status_change_dispatches_the_notification_email(
        self, report_officer_role, mocker, django_capture_on_commit_callbacks
    ):
        email_mock = mocker.patch(
            "external.email.EmailService.send_report_status_update"
        )
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory()
        report = HazardReportFactory(
            assigned_to=officer,
            reported_by=reporter,
            status=HazardReports.Status.UNDER_REVIEW,
            severity="P2",
        )

        with django_capture_on_commit_callbacks(execute=True):
            result = ReportService.update_authorized_assigned_report(
                user=officer,
                report_number=report.report_number,
                new_status_str="DISPATCHED",
                remarks="Crew deployed.",
            )

        assert result.is_success
        report.refresh_from_db()
        assert report.status == HazardReports.Status.DISPATCHED

        email_mock.assert_called_once()
        kwargs = email_mock.call_args.kwargs
        assert kwargs["to_email"] == reporter.email
        assert kwargs["report_number"] == report.report_number
        assert kwargs["old_status"] == HazardReports.Status.UNDER_REVIEW.label
        assert kwargs["new_status"] == HazardReports.Status.DISPATCHED.label
        assert " at " in kwargs["submitted_at"]
