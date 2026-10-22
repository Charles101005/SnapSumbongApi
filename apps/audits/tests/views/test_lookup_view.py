import pytest

from apps.audits.models import AuditLogs
from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestLookupAuditLogModulesView:
    def test_returns_every_module_choice(self, api_client, system_admin_role):
        user = UserFactory(role=system_admin_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/lookup/modules/")

        assert response.status_code == 200
        assert response.json() == [
            {"value": value, "label": label}
            for value, label in AuditLogs.ModuleType.choices
        ]

    def test_role_without_audit_permissions_is_denied(
        self, api_client, report_officer_role
    ):
        user = UserFactory(role=report_officer_role)

        api_client.force_authenticate(user=user)
        response = api_client.get("/audits/lookup/modules/")

        assert response.status_code == 403
