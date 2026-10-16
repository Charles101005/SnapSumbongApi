import pytest

from apps.accounts.tests.factories import UserFactory


CITIZENS_URL = '/accounts/citizens/'


@pytest.mark.django_db
class TestCitizenListView:
    def test_admin_can_list_citizens_paginated(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)
        api_client.force_authenticate(user=admin)

        response = api_client.get(CITIZENS_URL)

        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['user_number'] == citizen.user_number

    def test_list_excludes_staff_and_omits_role_field(
            self,
            api_client,
            system_admin_role,
            citizen_role,
            report_officer_role,
    ):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        UserFactory(role=citizen_role, is_staff=False)
        UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(CITIZENS_URL)

        data = response.json()
        assert data['count'] == 1
        assert 'role' not in data['results'][0]

    def test_role_id_filter_is_ignored_for_citizens(
            self,
            api_client,
            system_admin_role,
            citizen_role,
            report_officer_role,
    ):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        UserFactory(role=citizen_role, is_staff=False)
        UserFactory(role=report_officer_role, is_staff=False)
        api_client.force_authenticate(user=admin)

        response = api_client.get(CITIZENS_URL, {'role_id': report_officer_role.role_id})

        assert response.json()['count'] == 2

    def test_is_active_filter(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        active = UserFactory(role=citizen_role, is_active=True)
        UserFactory(role=citizen_role, is_active=False)
        api_client.force_authenticate(user=admin)

        response = api_client.get(CITIZENS_URL, {'is_active': 'true'})

        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['user_number'] == active.user_number

    def test_search_by_name(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        match = UserFactory(role=citizen_role, first_name='Unique', last_name='Findme')
        UserFactory(role=citizen_role, first_name='Other', last_name='Person')
        api_client.force_authenticate(user=admin)

        response = api_client.get(CITIZENS_URL, {'q': 'Findme'})

        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['user_number'] == match.user_number

    def test_permission_denied_without_read_all(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(CITIZENS_URL)

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(CITIZENS_URL)

        assert response.status_code == 401


@pytest.mark.django_db
class TestCitizenDetailView:
    def test_admin_can_read_citizen_detail(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)
        api_client.force_authenticate(user=admin)

        response = api_client.get(f'{CITIZENS_URL}{citizen.user_number}/')

        assert response.status_code == 200
        data = response.json()
        assert data['user_number'] == citizen.user_number
        assert data['role'] == citizen_role.role_name

    def test_unknown_user_number_returns_404(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(f'{CITIZENS_URL}USER-00000000-AAAAAA/')

        assert response.status_code == 404
        assert response.json()['error_code'] == 'USER_NOT_FOUND'

    def test_staff_user_number_returns_404(self, api_client, system_admin_role, report_officer_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(f'{CITIZENS_URL}{staff.user_number}/')

        assert response.status_code == 404

    def test_permission_denied_without_read_all(self, api_client, citizen_role):
        user = UserFactory(role=citizen_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(f'{CITIZENS_URL}USER-00000000-AAAAAA/')

        assert response.status_code == 403


@pytest.mark.django_db
class TestCitizenDetailPatch:
    def test_admin_can_deactivate_citizen(self, api_client, system_admin_role, citizen_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{CITIZENS_URL}{citizen.user_number}/',
            {'is_active': False},
            format='json',
        )

        assert response.status_code == 200
        citizen.refresh_from_db()
        assert citizen.is_active is False

    def test_unknown_user_number_returns_404(self, api_client, system_admin_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{CITIZENS_URL}USER-00000000-AAAAAA/',
            {'is_active': False},
            format='json',
        )

        assert response.status_code == 404

    def test_permission_denied_without_activate_or_deactivate(
            self,
            api_client,
            report_officer_role,
    ):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f'{CITIZENS_URL}USER-00000000-AAAAAA/',
            {'is_active': False},
            format='json',
        )

        assert response.status_code == 403

    def test_staff_only_fields_are_stripped_for_citizens(
            self,
            api_client,
            system_admin_role,
            citizen_role,
            mocker,
    ):
        require_mock = mocker.patch(
            'shared.authorization.service.AuthorizationService.require_perm',
        )
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{CITIZENS_URL}{citizen.user_number}/',
            {'is_active': False, 'role_id': 99999},
            format='json',
        )

        assert response.status_code == 200
        citizen.refresh_from_db()
        assert citizen.role_id == citizen_role.role_id
        assert require_mock.call_args.args[1].name == 'user:deactivate_any'
