import pytest

from apps.accounts.domain_errors.role_error import (
    PermissionNotFoundError,
    RoleAlreadyExistError,
    RoleInUseError,
)
from apps.accounts.exceptions.role_exception import (
    DeactivatedRoleModificationDeniedException,
    RoleNotFoundException,
    SystemProtectedRoleModificationDeniedException,
)
from apps.accounts.services import RoleService
from apps.accounts.tests.factories import PermissionFactory, RoleFactory, UserFactory
from apps.audits.models import AuditLogs
from apps.audits.services import AuditLogService


@pytest.fixture
def actor():
    return UserFactory(is_staff=True)


@pytest.mark.django_db
class TestListRolesForLookup:
    def test_returns_only_active_roles_with_minimal_fields(self):
        active = RoleFactory(role_name='Active Role')
        RoleFactory(role_name='Inactive Role', is_active=False)

        result = RoleService.list_roles_for_lookup()

        assert result.is_success
        rows = list(result.value)
        assert {'role_id', 'role_name'} <= set(rows[0].keys())
        role_names = [row['role_name'] for row in rows]
        assert 'Active Role' in role_names
        assert 'Inactive Role' not in role_names


@pytest.mark.django_db
class TestListGroupedPermissions:
    def test_groups_permissions_by_uppercased_module(self):
        PermissionFactory(permission_name='perm:a', description='Desc A', module='users')
        PermissionFactory(permission_name='perm:b', description='Desc B', module='users')

        result = RoleService.list_permissions_grouped_by_module()

        assert result.is_success
        grouped = result.value
        assert 'USERS' in grouped
        names = [entry['permission_name'] for entry in grouped['USERS']]
        assert 'perm:a' in names
        assert 'perm:b' in names
        assert all('description' in entry for entry in grouped['USERS'])


@pytest.mark.django_db
class TestListRoles:
    def test_filters_by_is_active(self):
        RoleFactory(role_name='Active Role', is_active=True)
        RoleFactory(role_name='Inactive Role', is_active=False)

        result = RoleService.list_roles({'is_active': True})

        assert result.is_success
        role_names = [role.role_name for role in result.value]
        assert 'Active Role' in role_names
        assert 'Inactive Role' not in role_names

    def test_searches_by_role_name(self):
        match = RoleFactory(role_name='Water District Officer')
        RoleFactory(role_name='Fire Safety Officer')

        result = RoleService.list_roles({'q': 'Water'})

        assert result.is_success
        assert list(result.value) == [match]

    def test_search_strips_whitespace(self):
        match = RoleFactory(role_name='Water District Officer')

        result = RoleService.list_roles({'q': '  Water  '})

        assert list(result.value) == [match]


@pytest.mark.django_db
class TestGetRole:
    def test_returns_role_when_found(self):
        role = RoleFactory()

        result = RoleService.get_role(role.role_id)

        assert result.is_success
        assert result.value == role

    def test_returns_none_when_missing(self):
        result = RoleService.get_role(999999)

        assert result.is_success
        assert result.value is None


@pytest.mark.django_db
class TestCreateRole:
    def test_creates_role_with_formatted_code_and_permissions(self, mocker):
        audit_mock = mocker.patch.object(AuditLogService, 'log_create')
        first = PermissionFactory(permission_name='perm:first')
        second = PermissionFactory(permission_name='perm:second')
        actor = UserFactory(is_staff=True)

        result = RoleService.create_role(
            actor=actor,
            role_name='  field officer ',
            description='Handles field operations',
            permission_names=['perm:first', 'perm:second'],
        )

        assert result.is_success
        role = result.value
        assert role.role_name == 'Field Officer'
        assert role.role_code == 'FIELD_OFFICER'
        assert role.description == 'Handles field operations'
        assert set(role.permissions.all()) == {first, second}
        audit_mock.assert_called_once()
        assert audit_mock.call_args.kwargs['module'] == AuditLogService.ModuleType.ROLE

    def test_duplicate_role_code_returns_error(self, mocker):
        mocker.patch.object(AuditLogService, 'log_create')
        RoleFactory(role_name='Field Officer', role_code='FIELD_OFFICER')
        actor = UserFactory(is_staff=True)

        result = RoleService.create_role(
            actor=actor,
            role_name='field officer',
            description='Duplicate',
            permission_names=[PermissionFactory().permission_name],
        )

        assert result.is_success is False
        assert result.error is RoleAlreadyExistError

    def test_unknown_permission_returns_error(self, mocker):
        mocker.patch.object(AuditLogService, 'log_create')
        PermissionFactory(permission_name='perm:valid')
        actor = UserFactory(is_staff=True)

        result = RoleService.create_role(
            actor=actor,
            role_name='Some Role',
            description='desc',
            permission_names=['perm:valid', 'perm:missing'],
        )

        assert result.is_success is False
        assert result.error is PermissionNotFoundError


@pytest.mark.django_db
class TestUpdateRole:
    def test_unknown_role_raises(self, actor):
        with pytest.raises(RoleNotFoundException):
            RoleService.update_role(actor=actor, role_id=999999, fields={})

    def test_protected_role_raises(self, actor):
        role = RoleFactory(is_protected=True)

        with pytest.raises(SystemProtectedRoleModificationDeniedException):
            RoleService.update_role(actor=actor, role_id=role.role_id, fields={'description': 'New'})

    def test_deactivated_role_raises(self, actor):
        role = RoleFactory(is_active=False)

        with pytest.raises(DeactivatedRoleModificationDeniedException):
            RoleService.update_role(actor=actor, role_id=role.role_id, fields={'description': 'New'})

    def test_rename_updates_name_and_code(self, actor):
        role = RoleFactory(role_name='Old Name', role_code='OLD_NAME')

        result = RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'role_name': 'New Name'},
        )

        assert result.is_success
        role.refresh_from_db()
        assert role.role_name == 'New Name'
        assert role.role_code == 'NEW_NAME'

    def test_rename_to_existing_code_returns_error(self, actor):
        RoleFactory(role_name='Taken Name', role_code='TAKEN_NAME')
        role = RoleFactory(role_name='Other Name', role_code='OTHER_NAME')

        result = RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'role_name': 'Taken Name'},
        )

        assert result.is_success is False
        assert result.error is RoleAlreadyExistError

    def test_blank_role_name_is_ignored(self, actor):
        role = RoleFactory(role_name='Keep Me', role_code='KEEP_ME')

        result = RoleService.update_role(actor=actor, role_id=role.role_id, fields={'role_name': '   '})

        assert result.is_success
        role.refresh_from_db()
        assert role.role_name == 'Keep Me'

    def test_description_update_strips_whitespace(self, actor):
        role = RoleFactory(description='Original')

        result = RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'description': '  Updated  '},
        )

        assert result.is_success
        role.refresh_from_db()
        assert role.description == 'Updated'

    def test_same_description_is_noop(self, actor):
        role = RoleFactory(description='Same')

        result = RoleService.update_role(actor=actor, role_id=role.role_id, fields={'description': 'Same'})

        assert result.is_success
        role.refresh_from_db()
        assert role.description == 'Same'

    def test_permission_names_replaces_permissions(self, actor):
        keep = PermissionFactory(permission_name='perm:keep')
        add = PermissionFactory(permission_name='perm:add')
        drop = PermissionFactory(permission_name='perm:drop')
        role = RoleFactory(permissions=[keep, drop])

        result = RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'permission_names': ['perm:keep', 'perm:add']},
        )

        assert result.is_success
        assert set(role.permissions.all()) == {keep, add}

    def test_unknown_permission_names_returns_error_and_keeps_old(self, actor):
        keep = PermissionFactory(permission_name='perm:keep')
        role = RoleFactory(permissions=[keep])

        result = RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'permission_names': ['perm:keep', 'perm:missing']},
        )

        assert result.is_success is False
        assert result.error is PermissionNotFoundError
        assert set(role.permissions.all()) == {keep}

    def test_permission_only_update_still_saves_updated_at(self, actor):
        perm = PermissionFactory()
        role = RoleFactory()

        result = RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'permission_names': [perm.permission_name]},
        )

        assert result.is_success
        assert list(role.permissions.all()) == [perm]

    def test_rename_to_equivalent_name_leaves_code_unchanged(self, actor):
        role = RoleFactory(role_name='Field Officer', role_code='FIELD_OFFICER')

        result = RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'role_name': 'field officer'},
        )

        assert result.is_success
        role.refresh_from_db()
        assert role.role_name == 'Field Officer'
        assert role.role_code == 'FIELD_OFFICER'

    def test_description_and_permissions_updated_together(self, actor):
        old_permission = PermissionFactory(permission_name='perm:old')
        new_permission = PermissionFactory(permission_name='perm:new')
        role = RoleFactory(description='Original', permissions=[old_permission])

        result = RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'description': 'Updated', 'permission_names': ['perm:new']},
        )

        assert result.is_success
        role.refresh_from_db()
        assert role.description == 'Updated'
        assert set(role.permissions.all()) == {new_permission}


@pytest.mark.django_db
class TestUpdateRoleAuditLogging:
    def test_rename_logs_update_with_changes(self, actor):
        role = RoleFactory(role_name='Old Name', role_code='OLD_NAME')

        RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'role_name': 'New Name'},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert log.module == AuditLogs.ModuleType.ROLE
        assert log.user_id == actor.user_id
        assert log.target_object == role
        assert log.payload['changes']['role_name'] == {'from': 'Old Name', 'to': 'New Name'}
        assert log.payload['changes']['role_code'] == {'from': 'OLD_NAME', 'to': 'NEW_NAME'}
        assert 'ROLE NEW_NAME' in log.description
        assert actor.user_number in log.description

    def test_permission_change_logs_added_and_removed(self, actor):
        keep = PermissionFactory(permission_name='perm:keep')
        add = PermissionFactory(permission_name='perm:add')
        drop = PermissionFactory(permission_name='perm:drop')
        role = RoleFactory(permissions=[keep, drop])

        RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'permission_names': ['perm:keep', 'perm:add']},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert log.payload['changes']['permissions'] == {
            'added': [add.permission_name],
            'removed': [drop.permission_name],
        }

    def test_no_change_logs_nothing(self, actor):
        role = RoleFactory(description='Same')

        RoleService.update_role(actor=actor, role_id=role.role_id, fields={'description': 'Same'})

        assert not AuditLogs.objects.exists()

    def test_permission_only_update_logs_update(self, actor):
        perm = PermissionFactory()
        role = RoleFactory()

        RoleService.update_role(
            actor=actor,
            role_id=role.role_id,
            fields={'permission_names': [perm.permission_name]},
        )

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.UPDATE)
        assert log.payload['changes']['permissions']['added'] == [perm.permission_name]


@pytest.mark.django_db
class TestDuplicateRole:
    def test_unknown_role_raises(self, actor):
        with pytest.raises(RoleNotFoundException):
            RoleService.duplicate_role(actor=actor, role_id=999999)

    def test_creates_suffixed_copy_with_same_permissions(self, actor):
        first = PermissionFactory()
        second = PermissionFactory()
        source = RoleFactory(
            role_name='Field Officer',
            role_code='FIELD_OFFICER',
            permissions=[first, second],
        )

        result = RoleService.duplicate_role(actor=actor, role_id=source.role_id)

        assert result.is_success
        duplicate = result.value
        assert duplicate.role_name == 'Field Officer_1'
        assert duplicate.role_code == 'FIELD_OFFICER_1'
        assert duplicate.description == 'Duplicate copy of Field Officer role.'
        assert set(duplicate.permissions.all()) == {first, second}

    def test_increments_counter_when_suffix_taken(self, actor):
        source = RoleFactory(role_name='Field Officer', role_code='FIELD_OFFICER')
        RoleFactory(role_name='Field Officer_1', role_code='FIELD_OFFICER_1')

        result = RoleService.duplicate_role(actor=actor, role_id=source.role_id)

        assert result.value.role_name == 'Field Officer_2'

    def test_strips_trailing_digits_from_base_name(self, actor):
        source = RoleFactory(role_name='Field Officer_3', role_code='FIELD_OFFICER_3')

        result = RoleService.duplicate_role(actor=actor, role_id=source.role_id)

        assert result.value.role_name == 'Field Officer_1'


@pytest.mark.django_db
class TestDuplicateRoleAuditLogging:
    def test_duplicate_logs_create_with_source(self, actor):
        permission = PermissionFactory(permission_name='perm:x')
        source = RoleFactory(
            role_name='Field Officer',
            role_code='FIELD_OFFICER',
            permissions=[permission],
        )

        result = RoleService.duplicate_role(actor=actor, role_id=source.role_id)

        duplicate = result.value
        log = AuditLogs.objects.get(action=AuditLogs.ActionType.CREATE)
        assert log.module == AuditLogs.ModuleType.ROLE
        assert log.target_object == duplicate
        assert log.payload['duplicated_from'] == {
            'role_id': source.role_id,
            'role_code': 'FIELD_OFFICER',
            'role_name': 'Field Officer',
        }
        assert 'initial_permissions' in log.payload


@pytest.mark.django_db
class TestDeactivateRole:
    def test_unknown_role_raises(self, actor):
        with pytest.raises(RoleNotFoundException):
            RoleService.deactivate_role(actor=actor, role_id=999999)

    def test_protected_role_raises(self, actor):
        role = RoleFactory(is_protected=True)

        with pytest.raises(SystemProtectedRoleModificationDeniedException):
            RoleService.deactivate_role(actor=actor, role_id=role.role_id)

    def test_already_inactive_role_is_noop(self, actor):
        role = RoleFactory(is_active=False)

        result = RoleService.deactivate_role(actor=actor, role_id=role.role_id)

        assert result.is_success
        role.refresh_from_db()
        assert role.is_active is False

    def test_role_in_use_returns_error(self, actor):
        role = RoleFactory()
        UserFactory(role=role)

        result = RoleService.deactivate_role(actor=actor, role_id=role.role_id)

        assert result.is_success is False
        assert result.error is RoleInUseError
        role.refresh_from_db()
        assert role.is_active is True

    def test_unused_role_is_deactivated(self, actor):
        role = RoleFactory()

        result = RoleService.deactivate_role(actor=actor, role_id=role.role_id)

        assert result.is_success
        role.refresh_from_db()
        assert role.is_active is False


@pytest.mark.django_db
class TestDeactivateRoleAuditLogging:
    def test_deactivation_logs_deactivate_action(self, actor):
        role = RoleFactory()

        RoleService.deactivate_role(actor=actor, role_id=role.role_id)

        log = AuditLogs.objects.get(action=AuditLogs.ActionType.DEACTIVATE)
        assert log.module == AuditLogs.ModuleType.ROLE
        assert log.target_object == role
        assert log.user_id == actor.user_id
        assert log.payload['changes']['is_active'] == {'from': True, 'to': False}
        assert f'ROLE {role.role_code}' in log.description
        assert actor.user_number in log.description

    def test_already_inactive_role_logs_nothing(self, actor):
        role = RoleFactory(is_active=False)

        RoleService.deactivate_role(actor=actor, role_id=role.role_id)

        assert not AuditLogs.objects.exists()
