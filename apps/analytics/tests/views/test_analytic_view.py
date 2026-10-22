import pytest

from apps.accounts.tests.factories import UserFactory, RoleFactory
from apps.reports.models import HazardReports
from apps.reports.tests.factories import HazardReportFactory


@pytest.mark.django_db
class TestHazardReportMetricsView:
    def _seed(self):
        owner = UserFactory()
        handler = UserFactory(is_staff=True)
        HazardReportFactory(
            reported_by=owner, assigned_to=handler, status=HazardReports.Status.NEW
        )
        HazardReportFactory(
            reported_by=UserFactory(),
            assigned_to=handler,
            status=HazardReports.Status.RESOLVED,
        )
        return owner, handler

    def test_supervisor_sees_every_report(self, api_client, supervisor_role):
        self._seed()
        user = UserFactory(role=supervisor_role, is_staff=True)

        api_client.force_authenticate(user=user)
        response = api_client.get("/analytics/hazard-report/")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert data["count_by_status"]["new"] == 1
        assert data["count_by_status"]["resolved"] == 1
        # Unrepresented statuses fall back to the serializer default.
        assert data["count_by_status"]["invalid"] == 0
        assert data["count_by_status"]["ongoing"] == 0

    def test_report_officer_sees_assigned_reports_only(
        self, api_client, report_officer_role
    ):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        outsider = UserFactory(role=report_officer_role, is_staff=True)
        HazardReportFactory(
            assigned_to=handler, status=HazardReports.Status.NEW
        )
        HazardReportFactory(
            assigned_to=handler, status=HazardReports.Status.RESOLVED
        )
        HazardReportFactory(
            assigned_to=outsider, status=HazardReports.Status.DISPATCHED
        )

        api_client.force_authenticate(user=handler)
        response = api_client.get("/analytics/hazard-report/")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert data["count_by_status"]["new"] == 1
        assert data["count_by_status"]["resolved"] == 1
        # The outsider's report must not leak into this officer's metrics.
        assert data["count_by_status"]["dispatched"] == 0

    def test_citizen_sees_own_reports_only(self, api_client, citizen_role):
        owner, _ = self._seed()
        citizen_user = UserFactory(role=citizen_role)
        HazardReportFactory(
            reported_by=citizen_user, status=HazardReports.Status.NEW
        )

        api_client.force_authenticate(user=citizen_user)
        response = api_client.get("/analytics/hazard-report/")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["count_by_status"]["new"] == 1

    def test_role_without_analytics_permissions_is_denied(self, api_client):
        self._seed()
        user = UserFactory(role=RoleFactory())

        api_client.force_authenticate(user=user)
        response = api_client.get("/analytics/hazard-report/")

        assert response.status_code == 403


@pytest.mark.django_db
class TestEmployeeMetricsView:
    def test_returns_handled_metrics(self, api_client, report_officer_role):
        handler = UserFactory(role=report_officer_role, is_staff=True)
        HazardReportFactory(
            assigned_to=handler, status=HazardReports.Status.RESOLVED
        )
        HazardReportFactory(assigned_to=handler, status=HazardReports.Status.NEW)
        viewer = UserFactory()

        api_client.force_authenticate(user=viewer)
        response = api_client.get(f"/analytics/employee/{handler.user_number}/")

        assert response.status_code == 200
        assert response.json() == {
            "total_reports_handled": 2,
            "total_reports_resolved": 1,
        }

    def test_staff_without_assignment_permission_conflicts(
        self, api_client, citizen_role
    ):
        staff = UserFactory(role=citizen_role, is_staff=True)
        viewer = UserFactory()

        api_client.force_authenticate(user=viewer)
        response = api_client.get(f"/analytics/employee/{staff.user_number}/")

        assert response.status_code == 409
        assert response.json()["error_code"] == "METRICS_NOT_APPLICABLE_TO_ROLE"

    def test_unknown_user_number_returns_404(self, api_client):
        viewer = UserFactory()

        api_client.force_authenticate(user=viewer)
        response = api_client.get("/analytics/employee/NO-SUCH-USER/")

        assert response.status_code == 404
        assert response.json()["error_code"] == "USER_NOT_FOUND"

    def test_citizen_number_is_not_visible_on_the_employee_endpoint(
        self, api_client, citizen_role
    ):
        citizen = UserFactory(role=citizen_role)
        viewer = UserFactory()

        api_client.force_authenticate(user=viewer)
        response = api_client.get(f"/analytics/employee/{citizen.user_number}/")

        assert response.status_code == 404
        assert response.json()["error_code"] == "USER_NOT_FOUND"


@pytest.mark.django_db
class TestCitizenMetricsView:
    def test_returns_submitted_metrics(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        handler = UserFactory(is_staff=True)
        HazardReportFactory(
            reported_by=citizen, assigned_to=handler, status=HazardReports.Status.RESOLVED
        )
        HazardReportFactory(
            reported_by=citizen, assigned_to=handler, status=HazardReports.Status.NEW
        )
        HazardReportFactory(reported_by=UserFactory(role=citizen_role))
        viewer = UserFactory()

        api_client.force_authenticate(user=viewer)
        response = api_client.get(f"/analytics/citizen/{citizen.user_number}/")

        assert response.status_code == 200
        assert response.json() == {
            "total_reports_submitted": 2,
            "total_reports_resolved": 1,
        }

    def test_unknown_user_number_returns_404(self, api_client):
        viewer = UserFactory()

        api_client.force_authenticate(user=viewer)
        response = api_client.get("/analytics/citizen/NO-SUCH-USER/")

        assert response.status_code == 404
        assert response.json()["error_code"] == "USER_NOT_FOUND"

    def test_staff_number_is_not_visible_on_the_citizen_endpoint(
        self, api_client, report_officer_role
    ):
        staff = UserFactory(role=report_officer_role, is_staff=True)
        viewer = UserFactory()

        api_client.force_authenticate(user=viewer)
        response = api_client.get(f"/analytics/citizen/{staff.user_number}/")

        assert response.status_code == 404
        assert response.json()["error_code"] == "USER_NOT_FOUND"
