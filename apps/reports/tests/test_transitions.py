import pytest

from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory
from apps.accounts.tests.factories import UserFactory


@pytest.mark.parametrize(
    "status,expected",
    [
        (HazardReports.Status.NEW, ["Under Review"]),
        (HazardReports.Status.ASSIGNED, ["Under Review"]),
        (HazardReports.Status.UNDER_REVIEW, ["On-Hold", "Dispatched"]),
        (HazardReports.Status.ON_HOLD, ["Under Review", "Dispatched", "Closed"]),
        (HazardReports.Status.DISPATCHED, ["Resolved", "On-Hold"]),
        (HazardReports.Status.RESOLVED, ["Closed"]),
        (HazardReports.Status.CLOSED, []),
    ],
)
def test_next_expected_statuses_matrix(status, expected):
    assert HazardReports.Status(status).get_next_expected_statuses() == expected


@pytest.mark.django_db
class TestNextExpectedStatusesInDetailEndpoint:
    # The staff modal reads next_expected_statuses from the detail response
    # to restrict its status dropdown (UI-only enforcement; the backend
    # update flow stays permissive).

    def test_staff_detail_includes_transition_matrix(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=report_officer_role)
        report = HazardReportFactory(
            status=HazardReports.Status.UNDER_REVIEW,
            assigned_to=officer,
            reported_by=reporter,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert response.data["next_expected_statuses"] == ["On-Hold", "Dispatched"]

    def test_staff_detail_closed_report_has_no_transitions(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)
        reporter = UserFactory(role=report_officer_role)
        report = HazardReportFactory(
            status=HazardReports.Status.CLOSED,
            assigned_to=officer,
            reported_by=reporter,
        )

        api_client.force_authenticate(user=officer)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert response.data["next_expected_statuses"] == []

    def test_citizen_detail_still_includes_transition_matrix(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        report = HazardReportFactory(
            status=HazardReports.Status.ON_HOLD,
            reported_by=citizen,
        )

        api_client.force_authenticate(user=citizen)
        response = api_client.get(f"/reports/{report.report_number}/")

        assert response.status_code == 200
        assert response.data["next_expected_statuses"] == [
            "Under Review",
            "Dispatched",
            "Closed",
        ]
