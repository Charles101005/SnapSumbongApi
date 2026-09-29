import string
import secrets

from django.db import transaction
from django.core.management import call_command
from devutils.base import DebugOnlyCommand

from apps.accounts.models import Users

def _generate_user_number(created_at) -> str:
    # USER-YYYYMMDD-6RandomBase36Chars

    PREFIX = "USER"
    SUFFIX_LENGTH = 6
    SUFFIX_CHOICES = string.digits + string.ascii_uppercase

    date_str = created_at.strftime("%Y%m%d")
    suffix_str = ''.join(secrets.choice(SUFFIX_CHOICES) for _ in range(SUFFIX_LENGTH))

    return f"{PREFIX}-{date_str}-{suffix_str}"

class Command(DebugOnlyCommand):
    def handle(self, *args, **options):
        start_migration = "0009_users_user_number"

        call_command('migrate', 'apps_accounts', start_migration)

        unpopulated_user_number = Users.objects.filter(user_number__isnull=True)

        if unpopulated_user_number.exists():

            with transaction.atomic():
                for user in unpopulated_user_number:
                    user.user_number = _generate_user_number(user.created_at)

                    while Users.objects.filter(user_number=user.user_number).exists():
                        user.user_number = _generate_user_number(user.created_at)

                    user.save(update_fields=['user_number'])

                    self.stdout.write(self.style.SUCCESS(
                        f"\tPopulated user {user.user_id} with number {user.user_number}"
                    ))

        else:
            self.stdout.write(self.style.SUCCESS(f"No unpopulated user numbers found."))

        call_command('migrate', 'apps_accounts')
        self.stdout.write(self.style.SUCCESS(f"Finished populating user numbers."))
