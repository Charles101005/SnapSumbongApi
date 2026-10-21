import string
from datetime import date

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.domain_errors.user_error import (
    IncorrectAccountCredentialsError,
    SelfUpdateDeniedError,
    UserNotFoundError,
)
from apps.accounts.exceptions.role_exception import RoleNotFoundException, SystemCitizenRoleMissingException
from apps.accounts.models import Users
from apps.accounts.services import AuthService, UserService
from apps.accounts.tests.factories import UserFactory, RoleFactory
from apps.audits.models import AuditLogs
from apps.audits.services import AuditLogService
from shared.authorization import AllPermissions
from external.storage import UploadIntent


@pytest.mark.django_db
class TestGenerateSecureTempPassword:
    def test_length_and_required_character_classes(self):
        password = UserService._generate_secure_temp_password()

        assert len(password) == 12
        assert any(char in string.ascii_lowercase for char in password)
        assert any(char in string.ascii_uppercase for char in password)
        assert any(char in string.digits for char in password)
        assert any(char in "!@#$%&*" for char in password)

    def test_accepts_custom_length(self):
        password = UserService._generate_secure_temp_password(length=20)

        assert len(password) == 20


@pytest.mark.django_db
class TestCreateVerifiedCitizen:
    def test_creates_active_citizen_with_citizen_role(self, citizen_role):
        result = UserService.create_verified_citizen(
            email='citizen@email.com',
            password_hash='already-hashed',
            last_name='Dela Cruz',
            first_name='Juan',
            middle_name='Santos',
        )

        assert result.is_success
        user = result.value
        assert user.email == 'citizen@email.com'
        assert user.role_id == citizen_role.role_id
        assert user.password == 'already-hashed'
        assert user.is_active is True

    def test_supports_missing_middle_name(self, citizen_role):
        result = UserService.create_verified_citizen(
            email='no-middle@email.com',
            password_hash='already-hashed',
            last_name='Dela Cruz',
            first_name='Juan',
        )

        assert result.is_success
        assert result.value.middle_name is None

    def test_raises_when_citizen_role_missing(self, citizen_role):
        citizen_role.delete()

        with pytest.raises(SystemCitizenRoleMissingException):
            UserService.create_verified_citizen(
                email='no-role@email.com',
                password_hash='already-hashed',
                last_name='Dela Cruz',
                first_name='Juan',
            )


@pytest.mark.django_db
class TestCreateStaff:
    def _staff_kwargs(self, role_id):
        return {
            'email': 'staff@email.com',
            'role_id': role_id,
            'last_name': 'Santos',
            'first_name': 'Maria',
            'middle_name': 'Cruz',
            'contact_number': '09171234567',
            'birth_date': date(1990, 1, 1),
            'gender': 'F',
            'street_address': '123 Rizal St',
            'region_code': '1300000000',
            'province_code': '1339000000',
            'city_code': '1339000000',
            'barangay_code': '1339010000',
        }

    def test_raises_when_role_not_found(self):
        with pytest.raises(RoleNotFoundException):
            UserService.create_staff(
                actor=UserFactory(),
                **self._staff_kwargs(role_id=999999),
            )

    def test_creates_staff_user_with_expected_fields(self, report_officer_role):
        actor = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.create_staff(
            actor=actor,
            **self._staff_kwargs(role_id=report_officer_role.role_id),
        )

        assert result.is_success
        user = result.value
        assert user.email == 'staff@email.com'
        assert user.role_id == report_officer_role.role_id
        assert user.is_staff is True
        assert user.must_change_password is True
        assert user.contact_number == '09171234567'
        assert user.gender == 'F'
        assert user.region_code == '1300000000'
        assert user.province_code == '1339000000'
        assert user.city_code == '1339000000'
        assert user.barangay_code == '1339010000'
        assert user.has_usable_password()

    def test_writes_employee_audit_log(self, report_officer_role, mocker):
        audit_mock = mocker.patch.object(AuditLogService, 'log_create')
        actor = UserFactory(role=report_officer_role, is_staff=True)

        UserService.create_staff(
            actor=actor,
            **self._staff_kwargs(role_id=report_officer_role.role_id),
        )

        audit_mock.assert_called_once()
        call_kwargs = audit_mock.call_args.kwargs
        created_user = Users.objects.get(email='staff@email.com')
        assert call_kwargs['module'] == AuditLogService.ModuleType.EMPLOYEE
        assert call_kwargs['target_identifier'] == created_user.user_number
        assert call_kwargs['payload']['assigned_role']['role_id'] == report_officer_role.role_id


@pytest.mark.django_db
class TestUnauthenticatedChangePassword:
    def test_unknown_email_returns_user_not_found(self):
        result = UserService.unauthenticated_change_password(
            email='unknown@email.com',
            new_password='NewPassword123',
        )

        assert result.is_success is False
        assert result.error is UserNotFoundError

    def test_inactive_user_returns_user_not_found(self, citizen_role):
        user = UserFactory(role=citizen_role, is_active=False)

        result = UserService.unauthenticated_change_password(
            email=user.email,
            new_password='NewPassword123',
        )

        assert result.is_success is False
        assert result.error is UserNotFoundError

    def test_success_updates_password(self, citizen_role):
        user = UserFactory(role=citizen_role)

        result = UserService.unauthenticated_change_password(
            email=user.email,
            new_password='NewPassword123',
        )

        assert result.is_success
        user.refresh_from_db()
        assert user.check_password('NewPassword123')


@pytest.mark.django_db
class TestGetNextStaffForAssignment:
    def test_returns_none_when_no_eligible_staff(self):
        assert UserService.get_next_staff_for_assignment({}) is None

    def test_ignores_inactive_staff(self, report_officer_role):
        UserFactory(role=report_officer_role, is_staff=True, is_active=False)

        assert UserService.get_next_staff_for_assignment({}) is None

    def test_ignores_staff_without_update_assigned_permission(self, citizen_role):
        UserFactory(role=citizen_role, is_staff=True)

        assert UserService.get_next_staff_for_assignment({}) is None

    def test_returns_eligible_staff(self, report_officer_role):
        staff = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.get_next_staff_for_assignment({})

        assert result == staff

    def test_picks_staff_with_fewest_active_reports(self, report_officer_role):
        busy = UserFactory(role=report_officer_role, is_staff=True)
        free = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.get_next_staff_for_assignment({
            busy.user_id: 5,
            free.user_id: 1,
        })

        assert result == free

    def test_defaults_unmapped_staff_to_zero(self, report_officer_role):
        mapped = UserFactory(role=report_officer_role, is_staff=True)
        unmapped = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.get_next_staff_for_assignment({mapped.user_id: 3})

        assert result == unmapped


@pytest.mark.django_db
class TestAuthenticatedChangePassword:
    def test_wrong_current_password_returns_error(self, citizen_role):
        user = UserFactory(role=citizen_role)

        result = UserService.authenticated_change_password(
            user=user,
            current_refresh_token='irrelevant',
            current_password='WrongPassword1',
            new_password='NewPassword123',
        )

        assert result.is_success is False
        assert result.error is IncorrectAccountCredentialsError
        user.refresh_from_db()
        assert user.check_password('Password2005')

    def test_success_changes_password_and_revokes_other_tokens(self, citizen_role, mocker):
        revoke_mock = mocker.patch.object(AuthService, 'revoke_other_refresh_tokens')
        user = UserFactory(role=citizen_role)

        result = UserService.authenticated_change_password(
            user=user,
            current_refresh_token='current-token',
            current_password='Password2005',
            new_password='NewPassword123',
        )

        assert result.is_success
        user.refresh_from_db()
        assert user.check_password('NewPassword123')
        revoke_mock.assert_called_once_with(user=user, current_refresh_token='current-token')


@pytest.mark.django_db
class TestDeactivateAccount:
    def test_active_account_is_deactivated(self, citizen_role):
        user = UserFactory(role=citizen_role)

        result = UserService.deactivate_account(user)

        assert result.is_success
        user.refresh_from_db()
        assert user.is_active is False

    def test_already_inactive_account_is_idempotent(self, citizen_role):
        user = UserFactory(role=citizen_role, is_active=False)

        result = UserService.deactivate_account(user)

        assert result.is_success
        user.refresh_from_db()
        assert user.is_active is False


@pytest.mark.django_db
class TestUpdateProfile:
    def test_updates_only_provided_fields(self, citizen_role):
        user = UserFactory(role=citizen_role, middle_name='Old')

        result = UserService.update_profile(
            user=user,
            fields={'first_name': 'Updated', 'middle_name': None},
        )

        assert result.is_success
        user.refresh_from_db()
        assert user.first_name == 'Updated'
        assert user.middle_name is None

    def test_empty_fields_is_noop(self, citizen_role):
        user = UserFactory(role=citizen_role, first_name='Original')

        result = UserService.update_profile(user=user, fields={})

        assert result.is_success
        user.refresh_from_db()
        assert user.first_name == 'Original'


@pytest.mark.django_db
class TestGetProfileImageUploadCredentials:
    def test_returns_upload_credentials_for_user_folder(self, citizen_role, mocker):
        expected = {'api_key': 'key', 'upload_url': 'url'}
        storage_mock = mocker.patch(
            'external.storage.StorageService.get_upload_credentials',
            return_value=expected,
        )
        user = UserFactory(role=citizen_role)

        result = UserService.get_profile_image_upload_credentials(user)

        assert result.is_success
        assert result.value == expected
        call_kwargs = storage_mock.call_args.kwargs
        assert call_kwargs['folder_path'] == UploadIntent.USER_PROFILES.value
        assert call_kwargs['intent'] == UploadIntent.USER_PROFILES
        assert len(call_kwargs['file_names']) == 1
        assert call_kwargs['file_names'][0].endswith('_pfp')

    def test_public_id_is_stable_per_user(self, citizen_role, mocker):
        storage_mock = mocker.patch(
            'external.storage.StorageService.get_upload_credentials',
            return_value={},
        )
        user = UserFactory(role=citizen_role)

        UserService.get_profile_image_upload_credentials(user)
        first_public_id = storage_mock.call_args.kwargs['file_names'][0]

        UserService.get_profile_image_upload_credentials(user)
        second_public_id = storage_mock.call_args.kwargs['file_names'][0]

        assert first_public_id == second_public_id


@pytest.mark.django_db
class TestListUsers:
    def test_separates_staff_from_citizens(self, citizen_role, report_officer_role):
        citizen = UserFactory(role=citizen_role, is_staff=False)
        staff = UserFactory(role=report_officer_role, is_staff=True)

        citizen_result = UserService.list_users(is_staff=False, query_filters={})
        staff_result = UserService.list_users(is_staff=True, query_filters={})

        assert citizen in list(citizen_result.value)
        assert staff not in list(citizen_result.value)
        assert staff in list(staff_result.value)
        assert citizen not in list(staff_result.value)

    def test_filters_by_is_active(self, citizen_role):
        active = UserFactory(role=citizen_role, is_active=True)
        UserFactory(role=citizen_role, is_active=False)

        result = UserService.list_users(is_staff=False, query_filters={'is_active': True})

        assert list(result.value) == [active]

    def test_filters_by_role_id(self, citizen_role, report_officer_role):
        UserFactory(role=citizen_role, is_staff=False)
        officer_as_citizen = UserFactory(role=report_officer_role, is_staff=False)

        result = UserService.list_users(
            is_staff=False,
            query_filters={'role_id': report_officer_role.role_id},
        )

        assert list(result.value) == [officer_as_citizen]

    def test_search_matches_multiple_tokens(self, citizen_role):
        match = UserFactory(
            role=citizen_role,
            first_name='Juan',
            last_name='Dela Cruz',
        )
        UserFactory(role=citizen_role, first_name='Pedro', last_name='Garcia')

        result = UserService.list_users(is_staff=False, query_filters={'q': 'Juan Cruz'})

        assert match in list(result.value)

    def test_search_no_match_returns_empty(self, citizen_role):
        UserFactory(role=citizen_role, first_name='Juan', last_name='Dela Cruz')

        result = UserService.list_users(is_staff=False, query_filters={'q': 'Nonexistent Name'})

        assert list(result.value) == []


@pytest.mark.django_db
class TestGetUser:
    def test_returns_staff_by_case_insensitive_user_number(self, report_officer_role):
        staff = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.get_user(user_number=staff.user_number.lower(), is_staff=True)

        assert result.is_success
        assert result.value == staff

    def test_returns_user_not_found_when_missing(self):
        result = UserService.get_user(user_number='USER-00000000-AAAAAA', is_staff=True)

        assert result.is_success is False
        assert result.error is UserNotFoundError

    def test_returns_user_not_found_for_wrong_is_staff_flag(self, report_officer_role):
        staff = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.get_user(user_number=staff.user_number, is_staff=False)

        assert result.is_success is False
        assert result.error is UserNotFoundError


@pytest.mark.django_db
class TestUpdateStaff:
    def _fields(self, **overrides):
        base = {'first_name': 'Updated'}
        base.update(overrides)
        return base

    def test_self_update_is_denied(self, report_officer_role):
        actor = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.update_staff(
            actor=actor,
            user_number=actor.user_number,
            fields=self._fields(),
        )

        assert result.is_success is False
        assert result.error is SelfUpdateDeniedError

    def test_self_update_is_case_insensitive(self, report_officer_role):
        actor = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.update_staff(
            actor=actor,
            user_number=actor.user_number.lower(),
            fields=self._fields(),
        )

        assert result.is_success is False
        assert result.error is SelfUpdateDeniedError

    def test_unknown_user_returns_not_found(self, system_admin_role):
        actor = UserFactory(role=system_admin_role, is_staff=True)

        result = UserService.update_staff(
            actor=actor,
            user_number='USER-00000000-AAAAAA',
            fields=self._fields(),
        )

        assert result.is_success is False
        assert result.error is UserNotFoundError

    def test_citizen_target_returns_not_found(self, system_admin_role, citizen_role):
        actor = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)

        result = UserService.update_staff(
            actor=actor,
            user_number=citizen.user_number,
            fields=self._fields(),
        )

        assert result.is_success is False
        assert result.error is UserNotFoundError

    def test_info_update_updates_fields(self, system_admin_role, report_officer_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields=self._fields(),
        )

        assert result.is_success
        target.refresh_from_db()
        assert target.first_name == 'Updated'

    def test_info_update_requires_update_any_permission(self, system_admin_role, report_officer_role, mocker):
        require_mock = mocker.patch(
            'shared.authorization.service.AuthorizationService.require_perm',
        )
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields=self._fields(),
        )

        assert require_mock.call_args.args[1] is AllPermissions.EMPLOYEES.UPDATE_ANY

    def test_info_update_denied_without_permission(self, report_officer_role, mocker):
        mocker.patch(
            'shared.authorization.service.AuthorizationService.require_perm',
            side_effect=PermissionDenied,
        )
        actor = UserFactory(role=report_officer_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)

        with pytest.raises(PermissionDenied):
            UserService.update_staff(
                actor=actor,
                user_number=target.user_number,
                fields=self._fields(),
            )

        target.refresh_from_db()
        assert target.first_name != 'Updated'

    def test_deactivate_requires_deactivate_any_permission(self, system_admin_role, mocker):
        require_mock = mocker.patch(
            'shared.authorization.service.AuthorizationService.require_perm',
        )
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=system_admin_role, is_staff=True)

        result = UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'is_active': False},
        )

        assert result.is_success
        target.refresh_from_db()
        assert target.is_active is False
        assert require_mock.call_args.args[1] is AllPermissions.EMPLOYEES.DEACTIVATE_ANY

    def test_activate_requires_activate_any_permission(self, system_admin_role, mocker):
        require_mock = mocker.patch(
            'shared.authorization.service.AuthorizationService.require_perm',
        )
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=system_admin_role, is_staff=True, is_active=False)

        result = UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'is_active': True},
        )

        assert result.is_success
        target.refresh_from_db()
        assert target.is_active is True
        assert require_mock.call_args.args[1] is AllPermissions.EMPLOYEES.ACTIVATE_ANY

    def test_role_change_updates_role(self, system_admin_role, report_officer_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'role_id': system_admin_role.role_id},
        )

        assert result.is_success
        target.refresh_from_db()
        assert target.role_id == system_admin_role.role_id

    def test_role_change_with_unknown_role_raises(self, system_admin_role, report_officer_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)

        with pytest.raises(RoleNotFoundException):
            UserService.update_staff(
                actor=actor,
                user_number=target.user_number,
                fields={'role_id': 999999},
            )

    def test_unchanged_fields_do_not_trigger_permission_checks(self, system_admin_role, report_officer_role, mocker):
        require_mock = mocker.patch(
            'shared.authorization.service.AuthorizationService.require_perm',
        )
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True, first_name='Same')

        result = UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'first_name': 'Same'},
        )

        assert result.is_success
        require_mock.assert_not_called()


@pytest.mark.django_db
class TestUpdateCitizen:
    def test_unknown_user_returns_not_found(self, system_admin_role):
        actor = UserFactory(role=system_admin_role, is_staff=True)

        result = UserService.update_citizen(
            actor=actor,
            user_number='USER-00000000-AAAAAA',
            fields={'is_active': False},
        )

        assert result.is_success is False
        assert result.error is UserNotFoundError

    def test_staff_target_returns_not_found(self, system_admin_role, report_officer_role):
        actor = UserFactory(role=system_admin_role, is_staff=True)
        staff = UserFactory(role=report_officer_role, is_staff=True)

        result = UserService.update_citizen(
            actor=actor,
            user_number=staff.user_number,
            fields={'is_active': False},
        )

        assert result.is_success is False
        assert result.error is UserNotFoundError

    def test_deactivate_citizen(self, system_admin_role, citizen_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)

        result = UserService.update_citizen(
            actor=actor,
            user_number=citizen.user_number,
            fields={'is_active': False},
        )

        assert result.is_success
        citizen.refresh_from_db()
        assert citizen.is_active is False

    def test_activate_citizen(self, system_admin_role, citizen_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False, is_active=False)

        result = UserService.update_citizen(
            actor=actor,
            user_number=citizen.user_number,
            fields={'is_active': True},
        )

        assert result.is_success
        citizen.refresh_from_db()
        assert citizen.is_active is True

    def test_noop_when_is_active_unchanged(self, system_admin_role, citizen_role, mocker):
        require_mock = mocker.patch(
            'shared.authorization.service.AuthorizationService.require_perm',
        )
        actor = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False, is_active=True)

        result = UserService.update_citizen(
            actor=actor,
            user_number=citizen.user_number,
            fields={'is_active': True},
        )

        assert result.is_success
        require_mock.assert_not_called()


@pytest.mark.django_db
class TestUpdateStaffAuditLogging:
    def test_info_update_logs_update_with_changes(self, system_admin_role, report_officer_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True, first_name='Original')

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'first_name': 'Updated'},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert log.module == AuditLogs.ModuleType.EMPLOYEE
        assert log.user_id == actor.user_id
        assert log.target_object == target
        assert log.payload['changes']['first_name'] == {'from': 'Original', 'to': 'Updated'}
        assert f'EMPLOYEE {target.user_number}' in log.description
        assert actor.user_number in log.description

    def test_deactivation_logs_deactivate_action(self, system_admin_role, report_officer_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'is_active': False},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert log.module == AuditLogs.ModuleType.EMPLOYEE
        assert log.target_object == target
        assert log.payload['changes']['is_active'] == {'from': True, 'to': False}
        assert f'EMPLOYEE {target.user_number} was deactivated by {actor.user_number}' in log.description

    def test_activation_logs_update_action(self, system_admin_role, report_officer_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True, is_active=False)

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'is_active': True},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert log.module == AuditLogs.ModuleType.EMPLOYEE
        assert log.payload['changes']['is_active'] == {'from': False, 'to': True}

    def test_role_reassignment_logs_role_change(self, system_admin_role, report_officer_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)
        new_role = RoleFactory(role_name='Reassignment Target', role_code='REASSIGNMENT_TARGET')

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'role_id': new_role.role_id},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert log.payload['changes']['role'] == {
            'from': {'role_id': report_officer_role.role_id, 'role_name': report_officer_role.role_name},
            'to': {'role_id': new_role.role_id, 'role_name': new_role.role_name},
        }

    def test_info_update_description_uses_friendly_field_labels(
        self, system_admin_role, report_officer_role, mocker,
    ):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'first_name': 'Updated', 'contact_number': '09990001111'},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert "(changed: First Name, Contact Number)" in log.description
        # Raw column names must not leak into the human-readable description
        assert "first_name" not in log.description

    def test_role_reassignment_description_names_both_roles(
        self, system_admin_role, report_officer_role, mocker,
    ):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)
        new_role = RoleFactory(role_name='Reassignment Target', role_code='REASSIGNMENT_TARGET')

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'role_id': new_role.role_id},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert (
            f"(changed: Role ({report_officer_role.role_name} → {new_role.role_name}))"
            in log.description
        )

    def test_deactivation_description_uses_friendly_field_labels(
        self, system_admin_role, report_officer_role, mocker,
    ):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True)

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'is_active': False},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert "(changed: Account Status)" in log.description
        assert "is_active" not in log.description

    def test_no_change_logs_nothing(self, system_admin_role, report_officer_role):
        actor = UserFactory(role=system_admin_role, is_staff=True)
        target = UserFactory(role=report_officer_role, is_staff=True, first_name='Same')

        UserService.update_staff(
            actor=actor,
            user_number=target.user_number,
            fields={'first_name': 'Same'},
        )

        assert not AuditLogs.objects.exists()


@pytest.mark.django_db
class TestUpdateCitizenAuditLogging:
    def test_deactivation_logs_deactivate_action(self, system_admin_role, citizen_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False)

        UserService.update_citizen(
            actor=actor,
            user_number=citizen.user_number,
            fields={'is_active': False},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert log.module == AuditLogs.ModuleType.USER
        assert log.user_id == actor.user_id
        assert log.target_object == citizen
        assert log.payload['changes']['is_active'] == {'from': True, 'to': False}
        assert log.description == f'{citizen.user_number} was deactivated by {actor.user_number}'

    def test_activation_logs_update_action(self, system_admin_role, citizen_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False, is_active=False)

        UserService.update_citizen(
            actor=actor,
            user_number=citizen.user_number,
            fields={'is_active': True},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert log.module == AuditLogs.ModuleType.USER
        assert log.payload['changes']['is_active'] == {'from': False, 'to': True}
        assert log.description == f'{citizen.user_number} was activated by {actor.user_number}'

    def test_noop_logs_nothing(self, system_admin_role, citizen_role, mocker):
        mocker.patch('shared.authorization.service.AuthorizationService.require_perm')
        actor = UserFactory(role=system_admin_role, is_staff=True)
        citizen = UserFactory(role=citizen_role, is_staff=False, is_active=True)

        UserService.update_citizen(
            actor=actor,
            user_number=citizen.user_number,
            fields={'is_active': True},
        )

        assert not AuditLogs.objects.exists()
