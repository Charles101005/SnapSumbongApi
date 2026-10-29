import pytest

from apps.accounts.models import Users
from apps.accounts.tests.factories import UserFactory
from external.storage import StorageService, UploadIntent


EMPLOYEES_URL = '/accounts/employees/'


def _valid_employee_payload(role_id, **overrides):
    payload = {
        'email': 'newstaff@email.com',
        'role_id': role_id,
        'last_name': 'Santos',
        'first_name': 'Maria',
        'middle_name': 'Cruz',
        'contact_number': '09171234567',
        'birth_date': '1990-01-01',
        'gender': 'F',
        'street_address': '123 Rizal St',
        'region_code': '1300000000',
        'province_code': '1339000000',
        'city_code': '1339000000',
        'barangay_code': '1339010000',
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestEmployeeListView:
    def test_admin_can_list_employees(self, api_client, system_admin_role, report_officer_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(EMPLOYEES_URL)

        assert response.status_code == 200
        data = response.json()
        # the requesting admin is itself staff, so both appear in the list
        assert data['count'] == 2
        rows = {row['user_number']: row for row in data['results']}
        assert rows[staff.user_number]['role'] == report_officer_role.role_name
        assert rows[admin.user_number]['role'] == system_admin_role.role_name

    def test_list_excludes_citizens(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)
        api_client.force_authenticate(user=admin)

        response = api_client.get(EMPLOYEES_URL)

        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['user_number'] == admin.user_number
        assert citizen.user_number not in [row['user_number'] for row in data['results']]

    def test_role_id_filter_applies_for_employees(
            self,
            api_client,
            system_admin_role,
            report_officer_role,
            supervisor_role,
    ):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        UserFactory(role=report_officer_role, is_staff=True)
        supervisor = UserFactory(role=supervisor_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(EMPLOYEES_URL, {'role_id': supervisor_role.role_id})

        data = response.json()
        assert data['count'] == 1
        assert data['results'][0]['user_number'] == supervisor.user_number

    def test_permission_denied_without_read_all(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(EMPLOYEES_URL)

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(EMPLOYEES_URL)

        assert response.status_code == 401


@pytest.mark.django_db
class TestEmployeeListPost:
    def test_admin_can_create_employee(self, api_client, system_admin_role, report_officer_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.post(
            EMPLOYEES_URL,
            _valid_employee_payload(report_officer_role.role_id),
            format='json',
        )

        assert response.status_code == 201
        data = response.json()
        assert data['email'] == 'newstaff@email.com'
        assert data['role'] == report_officer_role.role_name
        assert data['full_name'] == 'Santos, Maria C.'

    def test_created_employee_is_staff_and_must_change_password(
            self,
            api_client,
            system_admin_role,
            report_officer_role,
    ):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        api_client.post(
            EMPLOYEES_URL,
            _valid_employee_payload(report_officer_role.role_id),
            format='json',
        )

        created = Users.objects.get(email='newstaff@email.com')
        assert created.is_staff is True
        assert created.must_change_password is True
        assert created.has_usable_password()

    def test_duplicate_email_returns_400(self, api_client, system_admin_role, report_officer_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        UserFactory(email='newstaff@email.com')
        api_client.force_authenticate(user=admin)

        response = api_client.post(
            EMPLOYEES_URL,
            _valid_employee_payload(report_officer_role.role_id),
            format='json',
        )

        assert response.status_code == 400
        assert 'email' in response.json()

    def test_invalid_psgc_code_returns_400(self, api_client, system_admin_role, report_officer_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.post(
            EMPLOYEES_URL,
            _valid_employee_payload(report_officer_role.role_id, city_code='123'),
            format='json',
        )

        assert response.status_code == 400
        assert 'city_code' in response.json()

    def test_invalid_gender_returns_400(self, api_client, system_admin_role, report_officer_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.post(
            EMPLOYEES_URL,
            _valid_employee_payload(report_officer_role.role_id, gender='X'),
            format='json',
        )

        assert response.status_code == 400
        assert 'gender' in response.json()

    def test_permission_denied_without_create(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            EMPLOYEES_URL,
            _valid_employee_payload(report_officer_role.role_id),
            format='json',
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestEmployeeDetailView:
    def test_admin_can_read_employee_detail(
            self,
            api_client,
            system_admin_role,
            report_officer_role,
    ):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(f'{EMPLOYEES_URL}{staff.user_number}/')

        assert response.status_code == 200
        data = response.json()
        assert data['user_number'] == staff.user_number
        assert data['role'] == report_officer_role.role_name

    def test_citizen_user_number_returns_404(self, api_client, system_admin_role, citizen_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)
        api_client.force_authenticate(user=admin)

        response = api_client.get(f'{EMPLOYEES_URL}{citizen.user_number}/')

        assert response.status_code == 404

    def test_unknown_user_number_returns_404(self, api_client, system_admin_role):
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.get(f'{EMPLOYEES_URL}USER-00000000-AAAAAA/')

        assert response.status_code == 404

    def test_permission_denied_without_read_all(self, api_client, report_officer_role):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.get(f'{EMPLOYEES_URL}USER-00000000-AAAAAA/')

        assert response.status_code == 403


@pytest.mark.django_db
class TestEmployeeDetailPatch:
    def test_admin_can_update_employee_fields(
            self,
            api_client,
            system_admin_role,
            report_officer_role,
            mocker,
    ):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        admin = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{EMPLOYEES_URL}{staff.user_number}/',
            {'first_name': 'Updated', 'contact_number': '09999999999'},
            format='json',
        )

        assert response.status_code == 200
        staff.refresh_from_db()
        assert staff.first_name == 'Updated'
        assert staff.contact_number == '09999999999'

    def test_admin_can_update_profile_picture_and_street_address(
            self,
            api_client,
            system_admin_role,
            report_officer_role,
            mocker,
    ):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        admin = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)
        base_url = StorageService.get_expected_response_base_url()

        response = api_client.patch(
            f'{EMPLOYEES_URL}{staff.user_number}/',
            {
                'profile_picture': (
                    f'{base_url}{UploadIntent.USER_PROFILES.value}/new_pfp.jpg'
                ),
                'street_address': '456 Bonifacio Ave',
            },
            format='json',
        )

        assert response.status_code == 200
        staff.refresh_from_db()
        assert staff.profile_picture == (
            f'{base_url}{UploadIntent.USER_PROFILES.value}/new_pfp.jpg'
        )
        assert staff.street_address == '456 Bonifacio Ave'

    def test_admin_can_change_role(
            self,
            api_client,
            system_admin_role,
            report_officer_role,
            supervisor_role,
            mocker,
    ):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        admin = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{EMPLOYEES_URL}{staff.user_number}/',
            {'role_id': supervisor_role.role_id},
            format='json',
        )

        assert response.status_code == 200
        staff.refresh_from_db()
        assert staff.role_id == supervisor_role.role_id

    def test_change_to_unknown_role_returns_400(
            self,
            api_client,
            system_admin_role,
            report_officer_role,
            mocker,
    ):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        admin = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{EMPLOYEES_URL}{staff.user_number}/',
            {'role_id': 999999},
            format='json',
        )

        assert response.status_code == 400
        assert response.json()['error_code'] == 'ROLE_NOT_FOUND'

    def test_admin_can_deactivate_employee(
            self,
            api_client,
            system_admin_role,
            report_officer_role,
            mocker,
    ):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        admin = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{EMPLOYEES_URL}{staff.user_number}/',
            {'is_active': False},
            format='json',
        )

        assert response.status_code == 200
        staff.refresh_from_db()
        assert staff.is_active is False

    def test_self_update_returns_409(self, api_client, system_admin_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        admin = UserFactory(role=system_admin_role, is_staff=True)
        api_client.force_authenticate(user=admin)

        response = api_client.patch(
            f'{EMPLOYEES_URL}{admin.user_number}/',
            {'is_active': False},
            format='json',
        )

        assert response.status_code == 409
        assert response.json()['error_code'] == 'SELF_UPDATE_DENIED'

    def test_permission_denied_without_any_employee_patch_perm(
            self,
            api_client,
            report_officer_role,
    ):
        user = UserFactory(role=report_officer_role)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f'{EMPLOYEES_URL}USER-00000000-AAAAAA/',
            {'first_name': 'Updated'},
            format='json',
        )

        assert response.status_code == 403
