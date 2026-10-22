import pytest

from apps.accounts.tests.factories import UserFactory
from apps.reports.tests.factories import HazardReportFactory


@pytest.mark.django_db
class TestSystemAdminReportAccess:
    """System Admin holds report:read_all (not read_own/read_assigned), so
    the Operations overview must return the full report list instead of
    the 403 it used to hit before the permission was granted."""

    def test_system_admin_lists_every_report(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        report = HazardReportFactory()

        api_client.force_authenticate(user=admin)
        response = api_client.get("/reports/")

        assert response.status_code == 200
        report_numbers = [row["report_number"] for row in response.data["results"]]
        assert report.report_number in report_numbers

    def test_system_admin_reads_a_report_they_neither_filed_nor_own(
        self, api_client, system_admin_role, citizen_role
    ):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        reporter = UserFactory(role=citizen_role)
        report = HazardReportFactory(reported_by=reporter)

        api_client.force_authenticate(user=admin)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200


@pytest.mark.django_db
class TestRemarksHiddenFromCitizens:
    """Internal staff working notes (remarks) stay on the detail payload
    for staff only; citizens only ever see per-transition remarks inside
    status_timeline."""

    def test_citizen_detail_omits_remarks(self, api_client, citizen_role, report_officer_role):
        reporter = UserFactory(role=citizen_role)
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            reported_by=reporter,
            assigned_to=officer,
            remarks="Internal: likely duplicate of HZ-0001.",
        )

        api_client.force_authenticate(user=reporter)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert "remarks" not in response.data

    def test_staff_detail_keeps_remarks(self, api_client, citizen_role, report_officer_role):
        reporter = UserFactory(role=citizen_role)
        officer = UserFactory(role=report_officer_role, is_staff=True)
        report = HazardReportFactory(
            reported_by=reporter,
            assigned_to=officer,
            remarks="Internal: verify with DPWH before dispatch.",
        )

        api_client.force_authenticate(user=officer)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert response.data["remarks"] == "Internal: verify with DPWH before dispatch."
