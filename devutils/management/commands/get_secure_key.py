import secrets
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        print("Secure Key:", secrets.token_urlsafe(50))
        print("Please Clear Console.".upper())
