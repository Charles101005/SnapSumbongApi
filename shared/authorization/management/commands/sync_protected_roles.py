from django.core.management.base import BaseCommand

from shared.authorization.default_initial_role import AllDefaultRoles
from apps.accounts.models import Roles, Permissions


class Command(BaseCommand):
    def handle(self, *args, **options):
        for role_def in AllDefaultRoles.get_protected_roles():

            role, created = Roles.objects.update_or_create(
                role_code=role_def.code,
                defaults={
                    'role_name': role_def.name,
                    'description': role_def.description,
                }
            )

            perm_names = [perm.name for perm in role_def.permissions]
            perms = Permissions.objects.filter(permission_name__in=perm_names)

            role.permissions.set(perms)

            self.stdout.write(f"\t[{"Created" if created else "Updated"}] Protected Role: ({role_def.code})")

        self.stdout.write(self.style.SUCCESS("Protected roles successfully synced."))