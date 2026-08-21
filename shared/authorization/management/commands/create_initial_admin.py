from getpass import getpass
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Users, Roles
from shared.authorization.default_initial_role import AllDefaultRoles


class Command(BaseCommand):
    email = 'initial_admin@snapsumbong.com'
    first_name = 'Initial Admin'
    last_name = 'User'

    def handle(self, *args, **options):
        admin_role = Roles.objects.get_by_code_or_none(AllDefaultRoles.SYSTEM_ADMIN.code)

        if not admin_role:
            raise CommandError('No default System Admin role found.')

        if Users.objects.filter(role=admin_role).exists():
            raise CommandError('A System Admin account already exists.')

        while True:
            password = getpass('Password: ')

            if not password:
                print('\tPassword is required.')
                continue

            if len(password) < 8:
                print('\tPassword must be at least 8 characters.')
                continue

            password_confirm = getpass("Password (again): ")

            if password != password_confirm:
                print('\tPasswords do not match.')
                continue

            break


        Users.objects.create_user(
            email=self.email,
            password=password,
            role=admin_role,
            first_name=self.first_name,
            last_name=self.last_name,
            is_verified=True,
            is_staff=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f"Initial System Administrator account created. Login using '{self.email}' email."
        ))