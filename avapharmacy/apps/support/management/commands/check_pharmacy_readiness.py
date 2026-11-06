from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.support.models import ComplianceEvidence, OperationalReview, SiteSettings
from apps.support.checks import REQUIRED_COMPLIANCE_FIELDS, _is_missing


class Command(BaseCommand):
    help = 'Fail release when disclosures, catalog review or operational evidence are incomplete.'
    def handle(self, **options):
        site = SiteSettings.get_solo()
        gaps = [f'Missing disclosure: {f}' for f in REQUIRED_COMPLIANCE_FIELDS if _is_missing(getattr(site, f, ''))]
        evidence = set(ComplianceEvidence.objects.filter(verified_at__isnull=False, expires_at__gte=timezone.localdate(), status='active').values_list('evidence_type', flat=True))
        gaps += [f'Current independently reviewed evidence required: {kind}' for kind, _ in ComplianceEvidence.TYPE_CHOICES if kind not in evidence]
        areas = {x[0] for x in OperationalReview._meta.get_field('area').choices}
        complete = set(OperationalReview.objects.filter(completed_at__isnull=False, due_on__gte=timezone.localdate(), evidence__verified_at__isnull=False).values_list('area', flat=True))
        gaps += [f'Current operational review required: {x}' for x in sorted(areas-complete)]
        from apps.accounts.models import Pharmacist, User
        operators = Pharmacist.objects.filter(user__is_active=True, user__status='active', user__role__in=['pharmacist', 'admin']).select_related('user', 'credential_evidence')
        invalid = sum(not profile.credential_is_current for profile in operators)
        missing = User.objects.filter(role='pharmacist', is_active=True, status='active', pharmacist__isnull=True).count()
        if invalid or missing:
            gaps.append(f'Current pharmacist credentials required: {invalid} invalid profiles and {missing} missing profiles.')
        if gaps:
            raise CommandError('\n'.join(gaps))
        self.stdout.write('Recorded readiness gates passed. External PPB/professional/production verification is still required.')
