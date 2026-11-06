"""Catalogue supply eligibility, independent of internal review workflow labels."""
from django.utils import timezone
from django.db.models import Q


def prescription_required(variant):
    return bool(variant and (variant.requires_prescription or variant.prescription_classification in {'prescription', 'controlled'}))


def is_medicine(variant):
    return bool(variant and (variant.regulatory_scope == 'medicine' or prescription_required(variant) or variant.prescription_classification in {'otc', 'controlled'}))


def promotional_product(product):
    if getattr(product, 'requires_prescription', False):
        return False
    return not product.variants.filter(is_active=True).filter(
        Q(requires_prescription=True) |
        Q(prescription_classification__in=['prescription', 'controlled'])
    ).exists()


def supply_error(variant):
    if not variant:
        return 'Select a catalogue variant.'
    if not variant.is_active or not variant.product.is_active:
        return 'This product is inactive and cannot be supplied.'
    if variant.prescription_classification == 'controlled':
        return 'Controlled drugs cannot be supplied online.'
    if variant.regulatory_status in {'suspended', 'withdrawn'}:
        return 'This item has a suspended or withdrawn authorization.'
    if is_medicine(variant):
        if not all(str(getattr(variant, field, '') or '').strip() for field in
                   ['pil_version', 'pil_source_url', 'contraindications', 'side_effects', 'directions', 'warnings']):
            return 'Reviewed medicine safety information and PIL provenance are required.'
        if not variant.pil_reviewed_at or not variant.pil_reviewed_by_id:
            return 'Medicine safety information requires an attributable professional review.'
    from django.conf import settings
    if is_medicine(variant) and getattr(settings, 'REQUIRE_VERIFIED_OPERATIONAL_EVIDENCE', False):
        from apps.support.models import SiteSettings, ComplianceEvidence
        from apps.support.checks import REQUIRED_COMPLIANCE_FIELDS, _is_missing
        site = SiteSettings.get_solo()
        if any(_is_missing(getattr(site, field, '')) for field in REQUIRED_COMPLIANCE_FIELDS):
            return 'Pharmacy licensing disclosures are incomplete; medicine supply is on hold.'
        if not ComplianceEvidence.objects.filter(evidence_type='ppb_authorization', verified_at__isnull=False, status='active', expires_at__gte=timezone.localdate()).exists():
            return 'Current independently reviewed pharmacy authorization is required before medicine supply.'
    return None


def public_advertisement_allowed(link):
    from urllib.parse import urlparse, unquote
    from .models import Product
    parts = urlparse(str(link or '')).path.strip('/').split('/')
    if len(parts) > 1 and parts[0] in {'product', 'products'}:
        key = unquote(parts[1])
        query = Q(slug=key) | Q(sku=key)
        if key.isdecimal():
            query |= Q(pk=int(key))
        product = Product.objects.filter(query).first()
        return bool(product and promotional_product(product))
    return True


def medicine_inventory_rows(variant, rows):
    if not is_medicine(variant):
        return rows
    today = timezone.localdate()
    return [row for row in rows if row.batch_number.strip() and row.supplier.strip()
            and row.expiry_date and row.expiry_date >= today
            and (not row.store_listing_id or (row.store_listing.is_active and row.store_listing.store.is_active))]
