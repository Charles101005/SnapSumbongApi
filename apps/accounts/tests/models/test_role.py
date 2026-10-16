import pytest

from apps.accounts.models import Roles
from apps.accounts.tests.factories import RoleFactory


@pytest.mark.django_db
class TestRoleManager:
    def test_get_by_id_or_none_when_exists(self):
        role = RoleFactory()

        assert Roles.objects.get_by_id_or_none(role.role_id) == role

    def test_get_by_id_or_none_when_missing(self):
        assert Roles.objects.get_by_id_or_none(999999) is None

    def test_get_by_code_or_none_when_exists(self):
        role = RoleFactory(role_code='WATERS_OFFICER')

        assert Roles.objects.get_by_code_or_none('WATERS_OFFICER') == role

    def test_get_by_code_or_none_when_missing(self):
        assert Roles.objects.get_by_code_or_none('NON_EXISTENT_CODE') is None


class TestFormatRoleCode:
    @pytest.mark.parametrize(
        'role_name, expected',
        [
            ('System Admin', 'SYSTEM_ADMIN'),
            ('Report Officer', 'REPORT_OFFICER'),
            ('single', 'SINGLE'),
            ('  spaced   name  ', 'SPACED_NAME'),
        ],
    )
    def test_format_role_code(self, role_name, expected):
        assert Roles.format_role_code(role_name) == expected

