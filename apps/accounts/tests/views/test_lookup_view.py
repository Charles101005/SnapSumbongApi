import pytest

from apps.accounts.tests.factories import UserFactory


LOOKUP_ROLES_URL = '/accounts/lookup/roles/'
LOOKUP_PERMISSIONS_URL = '/accounts/lookup/permissions/'


@pytest.mark.django_db
class TestLookupRolesView:
    def test_admin_can_lookup_roles(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(LOOKUP_ROLES_URL)

        assert response.status_code == 200
        data = response.json()
        role_names = [row['role_name'] for row in data]
        assert citizen_role.role_name in role_names
        assert all('role_id' in row and 'role_name' in row for row in data)

    def test_supervisor_can_lookup_roles_via_audit_permission(
            self,
            api_client,
            supervisor_role,
    ):
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        api_client.force_authenticate(user=supervisor)

        response = api_client.get(LOOKUP_ROLES_URL)

        assert response.status_code == 200

    def test_permission_denied_for_report_officer(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=officer)

        response = api_client.get(LOOKUP_ROLES_URL)

        assert response.status_code == 403

    def test_permission_denied_for_citizen(self, api_client, citizen_role):
        citizen = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=citizen)

        response = api_client.get(LOOKUP_ROLES_URL)

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(LOOKUP_ROLES_URL)

        assert response.status_code == 401


@pytest.mark.django_db
class TestLookupPermissionsView:
    def test_admin_can_lookup_grouped_permissions(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(LOOKUP_PERMISSIONS_URL)

        assert response.status_code == 200
        data = response.json()
        assert 'USERS' in data
        assert 'ROLES' in data
        entry = data['USERS'][0]
        assert 'permission_name' in entry
        assert 'description' in entry

    def test_permission_denied_for_supervisor(self, api_client, supervisor_role):
        supervisor = UserFactory(role=supervisor_role)
        api_client.force_authenticate(user=supervisor)

        response = api_client.get(LOOKUP_PERMISSIONS_URL)

        assert response.status_code == 403

    def test_permission_denied_for_report_officer(self, api_client, report_officer_role):
        officer = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=officer)

        response = api_client.get(LOOKUP_PERMISSIONS_URL)

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(LOOKUP_PERMISSIONS_URL)

        assert response.status_code == 401
