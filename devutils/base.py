from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class DebugOnlyCommand(BaseCommand):
    def execute(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("This management command can only run in DEBUG mode.")

        return super().execute(*args, **options)