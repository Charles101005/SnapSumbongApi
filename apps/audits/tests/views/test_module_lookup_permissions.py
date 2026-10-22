import pytest

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestAuditModuleLookupPermissions:
    """GET /audits/lookup/modules/ must offer only the modules the
    requester's audit permissions unlock, mirroring the row-level filter
    in AuditLogService._authorized_audit_logs."""

    @staticmethod
    def _modules(api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/lookup/modules/")
        assert response.status_code == 200
        return {row["value"] for row in response.data}

    def test_system_admin_sees_every_module(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)

        modules = self._modules(api_client, admin)

        assert modules == {"USER", "EMPLOYEE", "ROLE", "REPORT"}

    def test_supervisor_sees_only_report_modules(self, api_client, supervisor_role):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)

        modules = self._modules(api_client, supervisor)

        assert modules == {"REPORT"}

    def test_report_officer_cannot_access_lookup(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role, is_staff=True)

        api_client.force_authenticate(user=officer)
        response = api_client.get("/audits/lookup/modules/")

        assert response.status_code == 403

    def test_citizen_cannot_access_lookup(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)

        api_client.force_authenticate(user=citizen)
        response = api_client.get("/audits/lookup/modules/")

        assert response.status_code == 403
