import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command

class Command(BaseCommand):
    help = "Starts a local secure HTTPS dev server with a custom local domain"

    backend_dev_url = 'api.localhost.test:8000'
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f'Starting secure HTTPS dev server on https://{self.backend_dev_url}/'))

        ssl_files_dir_path = os.path.join(settings.BASE_DIR, 'local_dev_ssl_files')

        cert_path = os.path.join(ssl_files_dir_path, 'app.localhost.test+1.pem')
        key_path = os.path.join(ssl_files_dir_path, 'app.localhost.test+1-key.pem')

        try:
            call_command(
                'runserver_plus',
                self.backend_dev_url,
                cert_file=str(cert_path),
                key_file=str(key_path),
            )
        except FileNotFoundError:
            raise CommandError(
                f"File not found. Please put SSL cert & key on directory '{ssl_files_dir_path}'"
            )