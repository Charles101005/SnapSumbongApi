import secrets
from devutils.base import DebugOnlyCommand


class Command(DebugOnlyCommand):
    def handle(self, *args, **options):
        print("Secure Key:", secrets.token_urlsafe(50))
        print("Please Clear Console.".upper())
