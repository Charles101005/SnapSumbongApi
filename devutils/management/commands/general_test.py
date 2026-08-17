from django.core.management.base import BaseCommand

from apps.accounts.models import Permissions


class Command(BaseCommand):
    def handle(self, *args, **options):
        print(Permissions.objects.all().count())