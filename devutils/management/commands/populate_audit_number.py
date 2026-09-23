import string
import secrets

from django.db import transaction
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.audits.models import AuditLogs

def _generate_audit_log_number(created_at) -> str:
    # LOG-YYYYMMDD-6RandomBase36Chars

    PREFIX = "LOG"
    SUFFIX_LENGTH = 6
    SUFFIX_CHOICES = string.digits + string.ascii_uppercase

    date_str = created_at.strftime("%Y%m%d")
    suffix_str = ''.join(secrets.choice(SUFFIX_CHOICES) for _ in range(SUFFIX_LENGTH))

    return f"{PREFIX}-{date_str}-{suffix_str}"

class Command(BaseCommand):
    def handle(self, *args, **options):
        start_migration = "0003_auditlogs_audit_log_number"

        call_command('migrate', 'apps_audits', start_migration)

        unpopulated_logs = AuditLogs.objects.filter(audit_log_number__isnull=True)

        if unpopulated_logs.exists():

            with transaction.atomic():
                for audit_log in unpopulated_logs:
                    audit_log.audit_log_number = _generate_audit_log_number(audit_log.created_at)

                    while AuditLogs.objects.filter(audit_log_number=audit_log.audit_log_number).exists():
                        audit_log.audit_log_number = _generate_audit_log_number(audit_log.created_at)

                    audit_log.save(update_fields=['audit_log_number'])

                    self.stdout.write(self.style.SUCCESS(
                        f"\tPopulated audit log {audit_log.audit_log_id} with number {audit_log.audit_log_number}"
                    ))

        else:
            self.stdout.write(self.style.SUCCESS(f"No unpopulated audit logs found."))

        call_command('migrate', 'apps_audits')
        self.stdout.write(self.style.SUCCESS(f"Finished populating audit log numbers."))
