import pytest

from apps.accounts.tests.factories import UserFactory
from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory


@pytest.mark.django_db
class TestReportListView:
    def test_citizen_list_hides_staff_only_fields(self, api_client, citizen_role):
        reporter = UserFactory(role=citizen_role)
        HazardReportFactory(
            reported_by=reporter,
            severity="P1",
            address="Sampaloc, Manila, Metro Manila",
        )

        api_client.force_authenticate(user=reporter)
        response = api_client.get("/reports/")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        row = data["results"][0]
        assert "severity" not in row
        assert "address" not in row
        assert "resolved_at" not in row
        assert row["report_number"].startswith("REPT-")

    def test_staff_status_filter_narrows_results(self, api_client, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        new_report = HazardReportFactory(
            status=HazardReports.Status.NEW, severity="P1"
        )
        HazardReportFactory(status=HazardReports.Status.DISPATCHED, severity="P2")

        api_client.force_authenticate(user=supervisor)
        response = api_client.get("/reports/", {"status": "NEW"})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["report_number"] == new_report.report_number

    def test_staff_search_filters_by_report_number(
        self, api_client, supervisor_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        match = HazardReportFactory(severity="P1")
        HazardReportFactory(severity="P2")

        api_client.force_authenticate(user=supervisor)
        response = api_client.get("/reports/", {"q": match.report_number})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["report_number"] == match.report_number
