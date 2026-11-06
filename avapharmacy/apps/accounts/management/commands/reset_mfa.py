"""Operator-only recovery after verifying the account holder's identity."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.accounts.models import AdminAuditLog, MFAChallenge, MFACredential, User
from apps.accounts.tokens import blacklist_user_refresh_tokens


class Command(BaseCommand):
    help = 'Reset MFA after independent identity verification; invalidates sessions and requires re-enrollment.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--reason', required=True, help='Identity verification / support reference (no secrets).')

    def handle(self, *args, **options):
        reason = options['reason'].strip()
        if not reason:
            raise CommandError('A non-empty reason is required.')
        with transaction.atomic():
            user = User.objects.select_for_update().filter(email__iexact=options['email'].strip()).first()
            if not user:
                raise CommandError('User not found.')
            MFACredential.objects.filter(user=user).delete()
            MFAChallenge.objects.filter(user=user).delete()
            blacklist_user_refresh_tokens(user)
            AdminAuditLog.objects.create(action='mfa_reset', entity_type='user', entity_id=str(user.pk),
                                         message='MFA reset by server operator', metadata={'reason': reason})
        self.stdout.write(self.style.SUCCESS('MFA reset. The next login requires enrollment.'))
