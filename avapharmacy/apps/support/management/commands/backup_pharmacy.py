"""Encrypted DB + media archive. Scheduling, offsite credentials and restore drill are operational duties."""
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create an age-encrypted database/private-media backup and copy it to configured offsite storage.'
    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--recipients-file', required=True)
        parser.add_argument('--offsite', required=True, help='rclone destination, e.g. approved-kenya-store:backups')

    def handle(self, *args, **options):
        for binary in ['pg_dump', 'age', 'rclone']:
            if not shutil.which(binary):
                raise CommandError(f'Required executable is unavailable: {binary}')
        db = settings.DATABASES['default']
        if 'postgresql' not in db['ENGINE']:
            raise CommandError('This backup command requires PostgreSQL.')
        recipients = Path(options['recipients_file'])
        if not recipients.is_file():
            raise CommandError('Provide an approved age public-recipient file; private keys belong off this host.')
        destination = Path(options['output_dir'])
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')
        output = destination / f'ava-{stamp}.tar.age'
        env = os.environ.copy()
        env['PGPASSWORD'] = str(db.get('PASSWORD') or '')
        try:
            with tempfile.TemporaryDirectory(prefix='ava-backup-') as tmp:
                os.chmod(tmp, 0o700)
                dump = Path(tmp)/'database.dump'
                subprocess.run(['pg_dump', '--format=custom', '--no-owner', '--host', str(db.get('HOST') or 'localhost'),
                    '--port', str(db.get('PORT') or 5432), '--username', str(db['USER']), '--file', str(dump), str(db['NAME'])], env=env, check=True, capture_output=True)
                archive = Path(tmp)/'archive.tar'
                with tarfile.open(archive, 'w') as tar:
                    tar.add(dump, arcname='database.dump')
                    media = Path(settings.MEDIA_ROOT)
                    if media.exists():
                        tar.add(media, arcname='media')
                subprocess.run(['age', '-R', str(recipients), '-o', str(output), str(archive)], check=True, capture_output=True)
                os.chmod(output, 0o600)
                subprocess.run(['rclone', 'copyto', str(output), options['offsite'].rstrip('/')+'/'+output.name], check=True, capture_output=True)
                subprocess.run(['rclone', 'check', str(destination), options['offsite'], '--one-way'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            raise CommandError('Backup or offsite verification failed. Inspect protected infrastructure logs; no success evidence was recorded.')
        self.stdout.write(json.dumps({'encrypted_archive': str(output), 'offsite_copy_verified': True,
                                     'restore_tested': False, 'completed_at': timezone.now().isoformat()}))
