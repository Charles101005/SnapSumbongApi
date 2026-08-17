from django.core.management.base import BaseCommand

from shared.authorization.default_initial_role import AllDefaultRoles
from apps.accounts.models import Roles, Permissions


class Command(BaseCommand):
    def handle(self, *args, **options):
        for role_def in AllDefaultRoles.get_flat_list():

            role, created = Roles.objects.get_or_create(
                role_code=role_def.code,
                defaults={
                    'role_name': role_def.name,
                    'description': role_def.description,
                    'is_protected': role_def.is_protected,
                }
            )

            if created:
                perm_names = [perm.name for perm in role_def.permissions]
                perms = Permissions.objects.filter(permission_name__in=perm_names)

                role.permissions.set(perms)

                self.stdout.write(self.style.SUCCESS(
                    f"\t[Created] Role: ({role_def.code}) created with default permissions."
                ))
            else:
                self.stdout.write(
                    f"\t[Skipped] Role: ({role_def.code}) already exists."
                )

        self.stdout.write(self.style.SUCCESS("Initial roles successfully created."))