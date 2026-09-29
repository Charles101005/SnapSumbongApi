from devutils.base import DebugOnlyCommand

from shared.authorization.default_initial_role import AllDefaultRoles
from apps.accounts.models import Roles, Permissions


class Command(DebugOnlyCommand):
    def handle(self, *args, **options):
        for role_def in AllDefaultRoles.get_flat_list():

            role, created = Roles.objects.update_or_create(
                role_code=role_def.code,
                defaults={
                    'role_name': role_def.name,
                    'description': role_def.description,
                    'is_protected': role_def.is_protected,
                }
            )

            perm_names = [perm.name for perm in role_def.permissions]
            perms = Permissions.objects.filter(permission_name__in=perm_names)

            role.permissions.set(perms)

            self.stdout.write(f"\t[{"Created" if created else "Updated"}] Initial Role: ({role_def.code})")

        self.stdout.write(self.style.SUCCESS("Initial roles successfully synced."))
