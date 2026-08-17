from django.core.management.base import BaseCommand

from apps.accounts.models.permission_model import Permissions
from shared.authorization.all_permissions_registry import AllPermissions


class Command(BaseCommand):
    def handle(self, *args, **options):
        active_perm_definitions = AllPermissions.get_flat_list()

        for perm in active_perm_definitions:
            Permissions.objects.update_or_create(
                permission_name=perm.name,
                defaults={
                    'description': perm.description,
                    'module': perm.module,
                }
            )

        active_perms_names = [perm.name for perm in active_perm_definitions]

        deleted_count, _ = Permissions.objects.exclude(permission_name__in=active_perms_names).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Synced {len(active_perms_names)} permissions. Deleted {deleted_count} permissions."
        ))
