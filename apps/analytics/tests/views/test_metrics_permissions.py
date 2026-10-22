import pytest

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestOverviewPermissions:
    """GET /analytics/overview/ follows the same scope as the status-count
    metrics: every default role holds one of read_all / read_assigned /
    read_own metrics, so all three may read it (each sees their own scope)."""

    @staticmethod
    def _get(api_client, user):
        api_client.force_authenticate(user=user)
        return api_client.get("/analytics/overview/")

    def test_system_admin_can_read_overview(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)

        response = self._get(api_client, admin)

        assert response.status_code == 200

    def test_report_officer_can_read_overview(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)

        response = self._get(api_client, officer)

        assert response.status_code == 200

    def test_citizen_can_read_overview(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)

        response = self._get(api_client, citizen)

        assert response.status_code == 200


@pytest.mark.django_db
class TestEmployeeMetricsPermissions:
    """GET /analytics/employee/<user_number>/ is gated on
    analytic:read_handler_performance — supervisors/admins inspect handler
    workloads; officers and citizens must get 403."""

    @staticmethod
    def _target_handler(report_officer_role):
        return UserFactory(role=report_officer_role, is_staff=True)

    @staticmethod
    def _get(api_client, user, target):
        api_client.force_authenticate(user=user)
        return api_client.get(f"/analytics/employee/{target.user_number}/")

    def test_system_admin_can_read_employee_metrics(
        self, api_client, system_admin_role, report_officer_role
    ):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        target = self._target_handler(report_officer_role)

        response = self._get(api_client, admin, target)

        assert response.status_code == 200
        assert "total_reports_handled" in response.data

    def test_supervisor_can_read_employee_metrics(
        self, api_client, supervisor_role, report_officer_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        target = self._target_handler(report_officer_role)

        response = self._get(api_client, supervisor, target)

        assert response.status_code == 200

    def test_report_officer_cannot_read_employee_metrics(
        self, api_client, report_officer_role
    ):
        requester = UserFactory(role=report_officer_role, is_staff=True)
        target = self._target_handler(report_officer_role)

        response = self._get(api_client, requester, target)

        assert response.status_code == 403

    def test_citizen_cannot_read_employee_metrics(
        self, api_client, citizen_role, report_officer_role
    ):
        requester = UserFactory(role=citizen_role)
        target = self._target_handler(report_officer_role)

        response = self._get(api_client, requester, target)

        assert response.status_code == 403


@pytest.mark.django_db
class TestCitizenMetricsPermissions:
    """GET /analytics/citizen/<user_number>/ is gated on user:read_all —
    only roles that may browse the citizen directory may read filing stats."""

    @staticmethod
    def _target_citizen(citizen_role):
        return UserFactory(role=citizen_role)

    @staticmethod
    def _get(api_client, user, target):
        api_client.force_authenticate(user=user)
        return api_client.get(f"/analytics/citizen/{target.user_number}/")

    def test_system_admin_can_read_citizen_metrics(
        self, api_client, system_admin_role, citizen_role
    ):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        target = self._target_citizen(citizen_role)

        response = self._get(api_client, admin, target)

        assert response.status_code == 200
        assert "total_reports_submitted" in response.data

    def test_supervisor_cannot_read_citizen_metrics(
        self, api_client, supervisor_role, citizen_role
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        target = self._target_citizen(citizen_role)

        response = self._get(api_client, supervisor, target)

        assert response.status_code == 403

    def test_citizen_cannot_read_citizen_metrics(
        self, api_client, citizen_role
    ):
        requester = UserFactory(role=citizen_role)
        target = self._target_citizen(citizen_role)

        response = self._get(api_client, requester, target)

        assert response.status_code == 403
