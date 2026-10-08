from django.core.management.base import BaseCommand

from apps.accounts.models.permission_model import Permissions
from shared.authorization.all_permissions_registry import AllPermissions


class Command(BaseCommand):
    def handle(self, *args, **options):
        active_perm_definitions = AllPermissions.get_flat_list()
        create_count = 0

        for perm in active_perm_definitions:
            _, created = Permissions.objects.update_or_create(
                permission_name=perm.name,
                defaults={
                    'description': perm.description,
                    'module': perm.module,
                }
            )

            if created:
                create_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"\t\t[Created] Permission: ({perm.name}) created"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"\t[Synced] Permission: ({perm.name}) synced"
                ))

        active_perms_names = [perm.name for perm in active_perm_definitions]

        deleted_perms = list(Permissions.objects.exclude(permission_name__in=active_perms_names))
        deleted_count, deleted_rows = Permissions.objects.exclude(permission_name__in=active_perms_names).delete()

        for perm in deleted_perms:
            self.stdout.write(self.style.SUCCESS(
                f"\t\t[Deleted] Permission: ({perm.permission_name}) deleted"
            ))

        for table, count in deleted_rows.items():
            self.stdout.write(self.style.SUCCESS(
                f"{table}: {count} rows"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nSynced {len(active_perms_names)} permissions."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Created {create_count} permissions | Deleted {deleted_count} permissions."
        ))
