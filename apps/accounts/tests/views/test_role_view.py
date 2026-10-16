import pytest

from apps.accounts.tests.factories import PermissionFactory, RoleFactory, UserFactory


ROLES_URL = '/accounts/roles/'


def _valid_role_payload(**overrides):
    permission = PermissionFactory(permission_name='perm:role_test')
    payload = {
        'role_name': 'Field Officer',
        'description': 'Handles field operations',
        'permission_names': [permission.permission_name],
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestRoleListView:
    def test_admin_can_list_roles_paginated(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(ROLES_URL)

        assert response.status_code == 200
        data = response.json()
        assert data['count'] >= 1
        assert 'results' in data
        entry = data['results'][0]
        assert 'role_id' in entry
        assert 'role_name' in entry
        assert 'is_active' in entry

    def test_search_filters_by_role_name(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        RoleFactory(role_name='Water District Officer')
        RoleFactory(role_name='Fire Safety Officer')
        api_client.force_authenticate(user=admin)

        response = api_client.get(ROLES_URL, {'q': 'Water'})

        data = response.json()
        names = [row['role_name'] for row in data['results']]
        assert 'Water District Officer' in names
        assert 'Fire Safety Officer' not in names

    def test_is_active_filter(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        RoleFactory(role_name='Active Custom', is_active=True)
        RoleFactory(role_name='Inactive Custom', is_active=False)
        api_client.force_authenticate(user=admin)

        response = api_client.get(ROLES_URL, {'is_active': 'false'})

        names = [row['role_name'] for row in response.json()['results']]
        assert 'Inactive Custom' in names
        assert 'Active Custom' not in names

    def test_permission_denied_without_read_all(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(ROLES_URL)

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(ROLES_URL)

        assert response.status_code == 401


@pytest.mark.django_db
class TestRoleListPost:
    def test_admin_can_create_role(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)
        payload = _valid_role_payload()

        response = api_client.post(ROLES_URL, payload, format='json')

        assert response.status_code == 201
        data = response.json()
        assert data['role_name'] == 'Field Officer'
        assert 'perm:role_test' in data['permissions']

    def test_duplicate_role_name_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        RoleFactory(role_name='Field Officer', role_code='FIELD_OFFICER')
        api_client.force_authenticate(user=admin)

        response = api_client.post(ROLES_URL, _valid_role_payload(), format='json')

        assert response.status_code == 400
        assert response.json()['error_code'] == 'ROLE_ALREADY_EXISTS'

    def test_unknown_permission_returns_404(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.post(
            ROLES_URL,
            _valid_role_payload(permission_names=['perm:missing']),
            format='json',
        )

        assert response.status_code == 404
        assert response.json()['error_code'] == 'PERMISSION_NOT_FOUND'

    def test_empty_permission_names_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.post(
            ROLES_URL,
            _valid_role_payload(permission_names=[]),
            format='json',
        )

        assert response.status_code == 400
        assert 'permission_names' in response.json()

    def test_permission_denied_without_create(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(ROLES_URL, _valid_role_payload(), format='json')

        assert response.status_code == 403


@pytest.mark.django_db
class TestRoleDetailView:
    def test_admin_can_read_role_detail(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        permission = PermissionFactory(permission_name='perm:detail')
        role = RoleFactory(role_name='Detail Role', permissions=[permission])
        api_client.force_authenticate(user=admin)

        response = api_client.get(f'{ROLES_URL}{role.role_id}/')

        assert response.status_code == 200
        data = response.json()
        assert data['role_id'] == role.role_id
        assert data['role_name'] == 'Detail Role'
        assert 'perm:detail' in data['permissions']
        assert 'created_at' in data

    def test_unknown_role_returns_success_with_detail_message(
            self,
            api_client,
            system_admin_role,
    ):
        # get_role returns DomainResult.success(None) when missing; the
        # response helper then emits the generic success payload.
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(f'{ROLES_URL}999999/')

        assert response.status_code == 200
        assert response.json() == {'detail': 'Operation completed successfully.'}

    def test_permission_denied_without_read_all(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(f'{ROLES_URL}1/')

        assert response.status_code == 403


@pytest.mark.django_db
class TestRoleDetailPatch:
    def test_admin_can_rename_role(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        role = RoleFactory(role_name='Old Name', role_code='OLD_NAME')
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{ROLES_URL}{role.role_id}/',
            {'role_name': 'New Name'},
            format='json',
        )

        assert response.status_code == 200
        role.refresh_from_db()
        assert role.role_name == 'New Name'
        assert role.role_code == 'NEW_NAME'

    def test_protected_role_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        role = RoleFactory(is_protected=True)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{ROLES_URL}{role.role_id}/',
            {'description': 'New'},
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'SYSTEM_PROTECTED_ROLE_MODIFICATION_DENIED'

    def test_deactivated_role_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        role = RoleFactory(is_active=False)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{ROLES_URL}{role.role_id}/',
            {'description': 'New'},
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'DEACTIVATED_ROLE_MODIFICATION_DENIED'

    def test_duplicate_name_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        RoleFactory(role_name='Taken Name', role_code='TAKEN_NAME')
        role = RoleFactory(role_name='Other Name', role_code='OTHER_NAME')
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{ROLES_URL}{role.role_id}/',
            {'role_name': 'Taken Name'},
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'ROLE_ALREADY_EXISTS'

    def test_permission_denied_without_update_any(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f'{ROLES_URL}1/',
            {'description': 'New'},
            format='json',
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestDuplicateRoleView:
    def test_admin_can_duplicate_role(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        permission = PermissionFactory()
        role = RoleFactory(role_name='Field Officer', role_code='FIELD_OFFICER', permissions=[permission])
        api_client.force_authenticate(user=admin)

        response = api_client.post(f'{ROLES_URL}duplicate/{role.role_id}/')

        assert response.status_code == 201
        data = response.json()
        assert data['role_name'] == 'Field Officer_1'
        assert len(data['permissions']) == 1

    def test_unknown_role_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.post(f'{ROLES_URL}duplicate/999999/')

        assert response.status_code == 400
        assert response.json()['error_code'] == 'ROLE_NOT_FOUND'

    def test_permission_denied_without_create(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(f'{ROLES_URL}duplicate/1/')

        assert response.status_code == 403


@pytest.mark.django_db
class TestDeactivateRoleView:
    def test_admin_can_deactivate_unused_role(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        role = RoleFactory()
        api_client.force_authenticate(user=admin)

        response = api_client.post(f'{ROLES_URL}deactivate/{role.role_id}/')

        assert response.status_code == 200
        role.refresh_from_db()
        assert role.is_active is False

    def test_role_in_use_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        role = RoleFactory()
        UserFactory(role=role)
        api_client.force_authenticate(user=admin)

        response = api_client.post(f'{ROLES_URL}deactivate/{role.role_id}/')

        assert response.status_code == 400
        assert response.json()['error_code'] == 'ROLE_IN_USE'

    def test_protected_role_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        role = RoleFactory(is_protected=True)
        api_client.force_authenticate(user=admin)

        response = api_client.post(f'{ROLES_URL}deactivate/{role.role_id}/')

        assert response.status_code == 400
        assert response.json()['error_code'] == 'SYSTEM_PROTECTED_ROLE_MODIFICATION_DENIED'

    def test_unknown_role_returns_400(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.post(f'{ROLES_URL}deactivate/999999/')

        assert response.status_code == 400
        assert response.json()['error_code'] == 'ROLE_NOT_FOUND'

    def test_permission_denied_without_deactivate_any(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(f'{ROLES_URL}deactivate/1/')

        assert response.status_code == 403
