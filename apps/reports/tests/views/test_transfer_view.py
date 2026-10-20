import pytest

from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestReportTransferView:
    def _report(self, status, officer, reporter):
        return HazardReportFactory(
            status=status,
            assigned_to=officer,
            reported_by=reporter,
        )

    def test_supervisor_can_transfer(
        self, api_client, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        new_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._report(
            HazardReports.Status.UNDER_REVIEW,
            current_officer,
            UserFactory(role=citizen_role),
        )

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            f"/reports/{report.report_number}/transfer/",
            {"assigned_to": new_officer.user_number, "remarks": "Workload rebalance."},
            format="json",
        )

        assert response.status_code == 200
        report.refresh_from_db()
        assert report.assigned_to_id == new_officer.user_id
        assert report.status == HazardReports.Status.UNDER_REVIEW

    def test_report_officer_cannot_transfer(
        self, api_client, report_officer_role, citizen_role
    ):
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        new_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._report(
            HazardReports.Status.ASSIGNED,
            current_officer,
            UserFactory(role=citizen_role),
        )

        api_client.force_authenticate(user=current_officer)
        response = api_client.post(
            f"/reports/{report.report_number}/transfer/",
            {"assigned_to": new_officer.user_number},
            format="json",
        )

        assert response.status_code == 403
        report.refresh_from_db()
        assert report.assigned_to_id == current_officer.user_id

    def test_citizen_cannot_transfer(
        self, api_client, report_officer_role, citizen_role
    ):
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        new_officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=citizen_role)
        report = self._report(
            HazardReports.Status.ASSIGNED,
            current_officer,
            reporter,
        )

        api_client.force_authenticate(user=reporter)
        response = api_client.post(
            f"/reports/{report.report_number}/transfer/",
            {"assigned_to": new_officer.user_number},
            format="json",
        )

        assert response.status_code == 403

    def test_transferring_closed_report_conflicts(
        self, api_client, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        new_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._report(
            HazardReports.Status.RESOLVED,
            current_officer,
            UserFactory(role=citizen_role),
        )

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            f"/reports/{report.report_number}/transfer/",
            {"assigned_to": new_officer.user_number},
            format="json",
        )

        assert response.status_code == 409
        assert response.data["error_code"] == "REPORT_NOT_TRANSFERABLE"

    def test_ineligible_target_is_rejected(
        self, api_client, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        citizen = UserFactory(role=citizen_role)
        report = self._report(
            HazardReports.Status.ASSIGNED,
            current_officer,
            UserFactory(role=citizen_role),
        )

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            f"/reports/{report.report_number}/transfer/",
            {"assigned_to": citizen.user_number},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error_code"] == "INVALID_TRANSFER_TARGET"

    def test_missing_target_is_rejected(
        self, api_client, supervisor_role, report_officer_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        current_officer = UserFactory(role=report_officer_role, is_staff=True)
        report = self._report(
            HazardReports.Status.ASSIGNED,
            current_officer,
            UserFactory(role=citizen_role),
        )

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            f"/reports/{report.report_number}/transfer/",
            {},
            format="json",
        )

        assert response.status_code == 400

    def test_unknown_report_returns_not_found(self, api_client, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        new_officer = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=supervisor)
        response = api_client.post(
            "/reports/REPT-00000000-XXXXXX/transfer/",
            {"assigned_to": new_officer.user_number},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error_code"] == "REPORT_DOES_NOT_EXIST"
