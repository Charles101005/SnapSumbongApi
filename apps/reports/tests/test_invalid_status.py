import pytest

from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestInvalidStatus:
    def test_invalid_requires_remarks(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=report_officer_role)
        report = HazardReportFactory(
            status=HazardReports.Status.UNDER_REVIEW,
            assigned_to=officer,
            reported_by=reporter,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"status": "INVALID"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error_code"] == "MANDATORY_REMARKS_STATUS"

    def test_invalid_with_remarks_succeeds(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=report_officer_role)
        report = HazardReportFactory(
            status=HazardReports.Status.UNDER_REVIEW,
            assigned_to=officer,
            reported_by=reporter,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"status": "INVALID", "remarks": "Location does not exist; photo is recycled."},
            format="json",
        )

        assert response.status_code == 200

        report.refresh_from_db()
        assert report.status == HazardReports.Status.INVALID
        assert report.remarks == "Location does not exist; photo is recycled."

    def test_invalid_is_terminal_no_further_transitions(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=report_officer_role)
        report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            assigned_to=officer,
            reported_by=reporter,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert response.data["next_expected_statuses"] == []

    def test_invalid_from_new_status(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=report_officer_role)
        report = HazardReportFactory(
            status=HazardReports.Status.NEW,
            assigned_to=officer,
            reported_by=reporter,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.patch(
            f"/reports/{report.report_number}/",
            {"status": "INVALID", "remarks": "Obvious fake report."},
            format="json",
        )

        assert response.status_code == 200

        report.refresh_from_db()
        assert report.status == HazardReports.Status.INVALID

    def test_invalid_is_phase_four_never_overdue(self):
        from datetime import timedelta
        from django.utils import timezone

        report = HazardReportFactory(
            status=HazardReports.Status.INVALID,
            due_at=timezone.now() - timedelta(days=5),
        )
        assert report.is_overdue is False

    def test_exclude_closed_also_excludes_invalid(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=report_officer_role)
        HazardReportFactory(
            status=HazardReports.Status.INVALID,
            assigned_to=officer,
            reported_by=reporter,
        )
        HazardReportFactory(
            status=HazardReports.Status.UNDER_REVIEW,
            assigned_to=officer,
            reported_by=reporter,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.get("/reports/", {"exclude_closed": "true"})

        assert response.status_code == 200
        statuses = [r["status"] for r in response.data["results"]]
        assert "Invalid" not in statuses
        assert "Under Review" in statuses
