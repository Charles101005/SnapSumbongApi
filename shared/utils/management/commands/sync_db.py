from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Running migrations..."))
        call_command('migrate')

        seed_commands = [
            "sync_perms",
            "create_initial_roles",
            "sync_hazard_categories",
        ]

        for command in seed_commands:
            self.stdout.write(self.style.NOTICE(f"Running {command}..."))
            call_command(command)

        self.stdout.write(self.style.SUCCESS("Synced database successfully."))
