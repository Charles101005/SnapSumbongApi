from django.core.management.base import BaseCommand

from apps.accounts.models import VerificationRequest


class Command(BaseCommand):
    def handle(self, *args, **options):
        obj = VerificationRequest.objects.get_for_update_or_none("email2@email.com", VerificationRequest.VerificationPurpose.REGISTRATION)

        print(dict(obj))