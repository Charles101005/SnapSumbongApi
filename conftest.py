import pytest
from rest_framework.test import APIClient
from django.conf import settings
from django.core.management import call_command

from apps.accounts.models import Roles
from shared.authorization.default_initial_role import AllDefaultRoles


def pytest_configure():
    settings.PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def citizen_role(seeded_rbac):
    return Roles.objects.get(
        role_code=AllDefaultRoles.CITIZEN.code
    )

@pytest.fixture
def report_officer_role(seeded_rbac):
    return Roles.objects.get(
        role_code=AllDefaultRoles.REPORT_OFFICER.code
    )

@pytest.fixture
def supervisor_role(seeded_rbac):
    return Roles.objects.get(
        role_code=AllDefaultRoles.SUPERVISOR.code
    )

@pytest.fixture
def system_admin_role(seeded_rbac):
    return Roles.objects.get(
        role_code=AllDefaultRoles.SYSTEM_ADMIN.code
    )

@pytest.fixture(scope='session')
def seeded_rbac(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command('sync_perms')
        call_command('create_initial_roles')
