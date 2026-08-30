from django.core.management.base import BaseCommand

from apps.accounts.models import VerificationRequest
import factory


class Command(BaseCommand):
    def handle(self, *args, **options):
        pass