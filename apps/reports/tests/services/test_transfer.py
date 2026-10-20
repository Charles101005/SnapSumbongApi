import pytest

from apps.audits.models import AuditLogs
from apps.reports.models import HazardReports
from apps.reports.services import ReportService
from apps.reports.domain_errors.report_error import (
    ReportNotTransferableError,
    InvalidTransferTargetError,
    AlreadyAssignedToTargetError,
)
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestTransferReport:
    def test_transfer_reassigns_officer_and_keeps_status(
        self, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        new_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=HazardReports.Status.UNDER_REVIEW,
            assigned_to=current_officer,
            reported_by=UserFactory(role=citizen_role),
        )

        result = ReportService.transfer_report(
            user=supervisor,
            report_number=report.report_number,
            assigned_to_user_number=new_officer.user_number,
            remarks="Rebalancing workload.",
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.assigned_to_id == new_officer.user_id
        assert report.status == HazardReports.Status.UNDER_REVIEW

    def test_transfer_writes_transfer_audit_log(
        self, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        new_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            assigned_to=current_officer,
            reported_by=UserFactory(role=citizen_role),
        )

        result = ReportService.transfer_report(
            user=supervisor,
            report_number=report.report_number,
            assigned_to_user_number=new_officer.user_number,
            remarks="Officer on leave.",
        )

        assert result.is_success

        transfer_logs = report.audit_logs.filter(action=AuditLogs.ActionType.TRANSFER)
        assert transfer_logs.count() == 1

        log = transfer_logs.first()
        assert log.user_id == supervisor.user_id
        assert log.payload["assignment_change"]["from"] == current_officer.email
        assert log.payload["assignment_change"]["to"] == new_officer.email
        assert log.payload["remarks"] == "Officer on leave."
        assert report.report_number in log.description

    def test_transfer_unassigned_report_records_unassigned_source(
        self, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        new_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=HazardReports.Status.NEW,
            assigned_to=None,
            reported_by=UserFactory(role=citizen_role),
        )

        result = ReportService.transfer_report(
            user=supervisor,
            report_number=report.report_number,
            assigned_to_user_number=new_officer.user_number,
        )

        assert result.is_success
        report.refresh_from_db()
        assert report.assigned_to_id == new_officer.user_id
        assert report.status == HazardReports.Status.NEW

        log = report.audit_logs.filter(action=AuditLogs.ActionType.TRANSFER).first()
        assert log.payload["assignment_change"]["from"] is None
        assert log.payload["assignment_change"]["to"] == new_officer.email

    @pytest.mark.parametrize("closed_status", [
        HazardReports.Status.RESOLVED,
        HazardReports.Status.CLOSED,
        HazardReports.Status.INVALID,
    ])
    def test_closed_reports_cannot_be_transferred(
        self, closed_status, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        new_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=closed_status,
            assigned_to=current_officer,
            reported_by=UserFactory(role=citizen_role),
        )

        result = ReportService.transfer_report(
            user=supervisor,
            report_number=report.report_number,
            assigned_to_user_number=new_officer.user_number,
        )

        assert result.is_success is False
        assert result.error is ReportNotTransferableError
        report.refresh_from_db()
        assert report.assigned_to_id == current_officer.user_id

    def test_cannot_transfer_to_non_staff(
        self, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            assigned_to=current_officer,
            reported_by=UserFactory(role=citizen_role),
        )

        result = ReportService.transfer_report(
            user=supervisor,
            report_number=report.report_number,
            assigned_to_user_number=citizen.user_number,
        )

        assert result.is_success is False
        assert result.error is InvalidTransferTargetError
        report.refresh_from_db()
        assert report.assigned_to_id == current_officer.user_id

    def test_cannot_transfer_to_inactive_staff(
        self, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        inactive_officer = UserFactory(
            role=report_officer_role, is_staff=True, is_active=False
        )
        report = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            assigned_to=current_officer,
            reported_by=UserFactory(role=citizen_role),
        )

        result = ReportService.transfer_report(
            user=supervisor,
            report_number=report.report_number,
            assigned_to_user_number=inactive_officer.user_number,
        )

        assert result.is_success is False
        assert result.error is InvalidTransferTargetError

    def test_cannot_transfer_to_staff_without_handler_role(
        self, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        other_supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            assigned_to=current_officer,
            reported_by=UserFactory(role=citizen_role),
        )

        result = ReportService.transfer_report(
            user=supervisor,
            report_number=report.report_number,
            assigned_to_user_number=other_supervisor.user_number,
        )

        assert result.is_success is False
        assert result.error is InvalidTransferTargetError

    def test_transfer_to_current_officer_is_rejected(
        self, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            status=HazardReports.Status.ASSIGNED,
            assigned_to=current_officer,
            reported_by=UserFactory(role=citizen_role),
        )

        result = ReportService.transfer_report(
            user=supervisor,
            report_number=report.report_number,
            assigned_to_user_number=current_officer.user_number,
        )

        assert result.is_success is False
        assert result.error is AlreadyAssignedToTargetError
