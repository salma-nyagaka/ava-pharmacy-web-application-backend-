"""Populate catalogue images without guessing product packshots.

The legacy POS exports contain barcodes but no image URLs.  This command first
gives every product and variant an honest category placeholder, then optionally
replaces those placeholders with front-of-pack images found by exact barcode in
the Open Facts product databases.
"""

from __future__ import annotations

from io import BytesIO
from difflib import SequenceMatcher
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import socket
import time
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.text import slugify

from apps.products.models import (
    IMAGE_SOURCE_MISSING,
    IMAGE_SOURCE_OPEN_FACTS,
    IMAGE_SOURCE_PLACEHOLDER,
    IMAGE_SOURCE_WEB_SCRAPE,
    Product,
    Variant,
)


OPEN_FACTS_ENDPOINT = 'https://world.openfoodfacts.org/api/v2/product/{barcode}.json'
ALLOWED_IMAGE_HOST_SUFFIXES = (
    'openfoodfacts.org',
    'openbeautyfacts.org',
    'openproductsfacts.org',
)
BLOCKED_SOURCE_HOST_SUFFIXES = (
    'aliexpress.com', 'ebay.com', 'facebook.com', 'instagram.com',
    'pinterest.com', 'poshmark.com', 'tiktok.com', 'temu.com', 'x.com',
)
MATCH_STOP_WORDS = {
    'a', 'an', 'and', 'at', 'by', 'for', 'from', 'in', 'of', 'on', 'product',
    'the', 'to', 'with', 'discontinued', 'discod',
}
PALETTE = (
    ('#E9F5FF', '#075985'),
    ('#F2F7EC', '#3F6212'),
    ('#FFF4E5', '#9A3412'),
    ('#F7EEFF', '#6B21A8'),
    ('#FFF0F4', '#9F1239'),
    ('#EAFBF7', '#0F766E'),
)


def gtin_check_digit_is_valid(value: str) -> bool:
    """Return whether an 8, 12, 13, or 14 digit GTIN has a valid check digit."""
    if not value.isdigit() or len(value) not in {8, 12, 13, 14}:
        return False
    if len(set(value)) == 1:
        return False
    payload = value[:-1]
    expected = int(value[-1])
    weighted_sum = sum(
        int(digit) * (3 if offset % 2 == 0 else 1)
        for offset, digit in enumerate(reversed(payload))
    )
    calculated = (10 - (weighted_sum % 10)) % 10
    return calculated == expected


def normalized_barcode(value: str) -> str:
    digits = re.sub(r'\D', '', str(value or ''))
    return digits if gtin_check_digit_is_valid(digits) else ''


def normalized_match_tokens(value: str) -> list[str]:
    normalized = re.sub(r'[^a-z0-9%]+', ' ', str(value or '').lower())
    return [token for token in normalized.split() if token not in MATCH_STOP_WORDS]


def image_result_match_score(product_name: str, result_title: str) -> float:
    """Return a conservative name/pack-size match score for a search result."""
    expected_tokens = normalized_match_tokens(product_name)
    result_tokens = normalized_match_tokens(result_title)
    if not expected_tokens or not result_tokens:
        return 0.0
    expected = set(expected_tokens)
    actual = set(result_tokens)
    recall = len(expected & actual) / len(expected)
    sequence = SequenceMatcher(None, ' '.join(expected_tokens), ' '.join(result_tokens)).ratio()
    expected_numbers = {token for token in expected if any(char.isdigit() for char in token)}
    actual_numbers = {token for token in actual if any(char.isdigit() for char in token)}
    if expected_numbers and not expected_numbers.intersection(actual_numbers):
        return 0.0
    number_score = 1.0 if not expected_numbers or expected_numbers <= actual_numbers else 0.5
    return (recall * 0.65) + (sequence * 0.25) + (number_score * 0.10)


def _font(size: int, *, bold: bool = False):
    filenames = ('Arial Bold.ttf', 'DejaVuSans-Bold.ttf') if bold else ('Arial.ttf', 'DejaVuSans.ttf')
    roots = (
        Path('/System/Library/Fonts/Supplemental'),
        Path('/Library/Fonts'),
        Path('/usr/share/fonts/truetype/dejavu'),
    )
    for root in roots:
        for filename in filenames:
            try:
                return ImageFont.truetype(str(root / filename), size)
            except OSError:
                continue
    try:
        return ImageFont.truetype(filenames[-1], size)
    except OSError:
        return ImageFont.load_default()


def create_placeholder(path: Path, category_name: str) -> None:
    """Create one reusable, explicitly labelled category placeholder."""
    palette_index = int(hashlib.sha256(category_name.encode('utf-8')).hexdigest()[:8], 16) % len(PALETTE)
    background, foreground = PALETTE[palette_index]
    canvas = Image.new('RGB', (1000, 1000), background)
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle((170, 150, 830, 690), radius=55, fill='white', outline=foreground, width=8)
    draw.rounded_rectangle((380, 270, 620, 610), radius=35, fill=background, outline=foreground, width=12)
    draw.rounded_rectangle((425, 210, 575, 290), radius=20, fill=foreground)
    draw.rectangle((475, 365, 525, 515), fill=foreground)
    draw.rectangle((425, 415, 575, 465), fill=foreground)

    title_font = _font(38, bold=True)
    category_font = _font(34, bold=True)
    small_font = _font(24)
    draw.text((500, 755), 'PRODUCT IMAGE COMING SOON', font=title_font, fill=foreground, anchor='mm')
    display_category = (category_name or 'Uncategorised').upper()
    if len(display_category) > 38:
        display_category = f'{display_category[:35]}...'
    draw.text((500, 820), display_category, font=category_font, fill=foreground, anchor='mm')
    draw.text((500, 890), 'AVA PHARMACY', font=small_font, fill=foreground, anchor='mm')

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, format='PNG', optimize=True)


class Command(BaseCommand):
    help = (
        'Populate every product and variant with labelled placeholders, then optionally '
        'replace them with exact-barcode images from Open Facts.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write files and database changes.')
        parser.add_argument(
            '--mode', choices=('placeholders', 'barcodes', 'web', 'all'), default='placeholders',
            help='Use local placeholders, exact-barcode Open Facts lookup, or strict web image matching.',
        )
        parser.add_argument('--limit', type=int, help='Maximum variants to check in barcode mode.')
        parser.add_argument('--offset', type=int, default=0, help='Start position for a resumable barcode batch.')
        parser.add_argument('--variant-id', type=int, help='Process one variant, useful for review and retries.')
        parser.add_argument(
            '--category',
            help='Limit barcode or web acquisition to one exact category slug.',
        )
        parser.add_argument(
            '--request-delay', type=float, default=4.1,
            help='Seconds between product API calls. The default stays below the documented 15/min limit.',
        )
        parser.add_argument(
            '--web-request-delay', type=float, default=1.5,
            help='Seconds between web image searches.',
        )
        parser.add_argument(
            '--minimum-match-score', type=float, default=0.78,
            help='Minimum 0-1 title similarity accepted for a scraped image.',
        )
        parser.add_argument('--force', action='store_true', help='Replace existing non-placeholder images too.')

    def handle(self, *args, **options):
        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                'Dry run: no files or rows changed. Add --apply after reviewing the summary.'
            ))

        mode = options['mode']
        if mode in {'placeholders', 'all'}:
            self._populate_placeholders(apply=options['apply'], force=options['force'])
        if mode in {'barcodes', 'all'}:
            self._populate_barcode_images(
                apply=options['apply'],
                force=options['force'],
                limit=options['limit'],
                offset=max(options['offset'], 0),
                request_delay=max(options['request_delay'], 4.1),
                variant_id=options['variant_id'],
                category_slug=options['category'],
            )
        if mode in {'web', 'all'}:
            self._populate_web_images(
                apply=options['apply'],
                force=options['force'],
                limit=options['limit'],
                offset=max(options['offset'], 0),
                request_delay=max(options['web_request_delay'], 0.5),
                minimum_score=min(max(options['minimum_match_score'], 0.0), 1.0),
                variant_id=options['variant_id'],
                category_slug=options['category'],
            )

    def _populate_placeholders(self, *, apply: bool, force: bool):
        products = list(Product.objects.prefetch_related('variants__category').order_by('pk'))
        product_updates = []
        variant_updates = []
        placeholder_paths: dict[str, str] = {}
        now = timezone.now()

        for product in products:
            variants = list(product.variants.all())
            representative = next((variant for variant in variants if variant.category_id), None)
            category = representative.category if representative else None
            category_name = category.name if category else 'Uncategorised'
            category_slug = category.slug if category else 'uncategorised'
            rel_path = f'products/placeholders/{slugify(category_slug) or "uncategorised"}.png'
            placeholder_paths[rel_path] = category_name

            can_replace_product = force or not product.image or product.image_source in {
                IMAGE_SOURCE_MISSING, IMAGE_SOURCE_PLACEHOLDER,
            }
            if can_replace_product:
                product.image = rel_path
                product.image_source = IMAGE_SOURCE_PLACEHOLDER
                product.image_source_url = ''
                product.image_source_page_url = ''
                product.image_verified = False
                product.image_checked_at = now
                product_updates.append(product)

            for variant in variants:
                can_replace_variant = force or not variant.image or variant.image_source in {
                    IMAGE_SOURCE_MISSING, IMAGE_SOURCE_PLACEHOLDER,
                }
                if not can_replace_variant:
                    continue
                variant_category = variant.category
                variant_name = variant_category.name if variant_category else category_name
                variant_slug = variant_category.slug if variant_category else category_slug
                variant_rel_path = f'products/placeholders/{slugify(variant_slug) or "uncategorised"}.png'
                placeholder_paths[variant_rel_path] = variant_name
                variant.image = variant_rel_path
                variant.image_source = IMAGE_SOURCE_PLACEHOLDER
                variant.image_source_url = ''
                variant.image_source_page_url = ''
                variant.image_verified = False
                variant.image_checked_at = now
                variant_updates.append(variant)

        self.stdout.write(
            f'Placeholder plan: {len(placeholder_paths)} reusable assets, '
            f'{len(product_updates)} products, {len(variant_updates)} variants.'
        )
        if not apply:
            return

        media_root = Path(settings.MEDIA_ROOT)
        for rel_path, category_name in placeholder_paths.items():
            path = media_root / rel_path
            if force or not path.exists():
                create_placeholder(path, category_name)

        fields = (
            'image', 'image_source', 'image_source_url', 'image_source_page_url',
            'image_verified', 'image_checked_at',
        )
        with transaction.atomic():
            Product.objects.bulk_update(product_updates, fields, batch_size=1000)
            Variant.objects.bulk_update(variant_updates, fields, batch_size=1000)
        self.stdout.write(self.style.SUCCESS('All catalogue records now have a visible image asset.'))

    def _populate_barcode_images(
        self, *, apply: bool, force: bool, limit: int | None, offset: int,
        request_delay: float, variant_id: int | None, category_slug: str | None,
    ):
        queryset = Variant.objects.select_related('product').order_by('pk')
        if variant_id:
            queryset = queryset.filter(pk=variant_id)
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        variants_by_barcode: dict[str, list[Variant]] = {}
        for variant in queryset.iterator(chunk_size=1000):
            barcode = normalized_barcode(variant.barcode or variant.product.barcode)
            if barcode:
                variants_by_barcode.setdefault(barcode, []).append(variant)
        barcodes = list(variants_by_barcode)[offset:offset + limit if limit else None]
        eligible_by_barcode = {
            barcode: [
                variant for variant in variants_by_barcode[barcode]
                if force or variant.image_source in (IMAGE_SOURCE_MISSING, IMAGE_SOURCE_PLACEHOLDER)
            ]
            for barcode in barcodes
        }
        eligible_by_barcode = {
            barcode: variants for barcode, variants in eligible_by_barcode.items() if variants
        }
        self.stdout.write(
            f'Barcode plan: inspect {len(eligible_by_barcode)} unique, checksum-valid GTINs '
            f'covering {sum(len(variants) for variants in eligible_by_barcode.values())} variants '
            f'(offset {offset}).'
        )
        if not apply:
            return

        session = requests.Session()
        session.headers.update({
            'User-Agent': os.getenv(
                'CATALOG_IMAGE_USER_AGENT', 'AvaPharmacyCatalog/1.0 (info@avapharmacy.co.ke)'
            ),
            'Accept': 'application/json,image/*',
        })
        matched = 0
        unavailable = 0
        failed = 0
        checked = 0
        product_promotions: dict[int, Variant] = {}

        for barcode, variants in eligible_by_barcode.items():
            checked += 1
            try:
                image_url = self._lookup_open_facts(session, barcode)
                if not image_url:
                    unavailable += 1
                    for variant in variants:
                        self._mark_checked(variant)
                else:
                    rel_path = self._download_packshot(session, barcode, image_url)
                    for variant in variants:
                        self._assign_exact_image(variant, rel_path, image_url)
                        product_promotions.setdefault(variant.product_id, variant)
                        matched += 1
            except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
                failed += 1
                self.stderr.write(f'  {barcode}: {exc}')
            if checked < len(eligible_by_barcode):
                time.sleep(request_delay)

        for variant in product_promotions.values():
            product = variant.product
            if force or product.image_source in {IMAGE_SOURCE_MISSING, IMAGE_SOURCE_PLACEHOLDER}:
                product.image = variant.image.name
                product.image_source = IMAGE_SOURCE_OPEN_FACTS
                product.image_source_url = variant.image_source_url
                product.image_source_page_url = variant.image_source_page_url
                product.image_verified = False
                product.image_checked_at = variant.image_checked_at
                product.save(update_fields=(
                    'image', 'image_source', 'image_source_url', 'image_source_page_url', 'image_verified',
                    'image_checked_at', 'updated_at',
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Barcode batch complete: {matched} variants matched, '
            f'{unavailable} GTINs unavailable, {failed} GTINs failed.'
        ))

    @staticmethod
    def _lookup_open_facts(session: requests.Session, barcode: str) -> str:
        response = session.get(
            OPEN_FACTS_ENDPOINT.format(barcode=barcode),
            params={
                'fields': 'code,product_name,image_front_url,image_url',
                'product_type': 'all',
            },
            timeout=20,
        )
        if response.status_code == 404:
            return ''
        response.raise_for_status()
        payload = response.json()
        if payload.get('status') != 1:
            return ''
        product = payload.get('product') or {}
        return str(product.get('image_front_url') or product.get('image_url') or '').strip()

    @staticmethod
    def _download_packshot(session: requests.Session, barcode: str, image_url: str) -> str:
        host = (urlparse(image_url).hostname or '').lower()
        if not any(host == suffix or host.endswith(f'.{suffix}') for suffix in ALLOWED_IMAGE_HOST_SUFFIXES):
            raise ValueError(f'rejected image host {host!r}')
        response = session.get(image_url, timeout=30)
        response.raise_for_status()
        if len(response.content) > 12 * 1024 * 1024:
            raise ValueError('image exceeds the 12 MB download limit')
        source = Image.open(BytesIO(response.content))
        source.load()
        source = ImageOps.exif_transpose(source).convert('RGB')
        source.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (1000, 1000), 'white')
        canvas.paste(source, ((1000 - source.width) // 2, (1000 - source.height) // 2))

        rel_path = f'products/catalog/{barcode}.webp'
        path = Path(settings.MEDIA_ROOT) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(path, 'WEBP', quality=88, method=6)
        return rel_path

    @staticmethod
    def _assign_exact_image(variant: Variant, rel_path: str, image_url: str):
        variant.image = rel_path
        variant.image_source = IMAGE_SOURCE_OPEN_FACTS
        variant.image_source_url = image_url
        variant.image_source_page_url = ''
        variant.image_verified = False
        variant.image_checked_at = timezone.now()
        variant.save(update_fields=(
            'image', 'image_source', 'image_source_url', 'image_source_page_url', 'image_verified',
            'image_checked_at', 'updated_at',
        ))

    @staticmethod
    def _mark_checked(variant: Variant):
        variant.image_checked_at = timezone.now()
        variant.save(update_fields=('image_checked_at', 'updated_at'))

    def _populate_web_images(
        self, *, apply: bool, force: bool, limit: int | None, offset: int,
        request_delay: float, minimum_score: float, variant_id: int | None,
        category_slug: str | None,
    ):
        queryset = Variant.objects.select_related('product', 'product__brand').order_by(
            F('product__brand_id').asc(nulls_last=True),
            'product__brand__name',
            'product__name',
            'pk',
        )
        if variant_id:
            queryset = queryset.filter(pk=variant_id)
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        batch = list(queryset[offset:offset + limit if limit else None])
        variants = [
            variant for variant in batch
            if force or variant.image_source in (IMAGE_SOURCE_MISSING, IMAGE_SOURCE_PLACEHOLDER)
        ]
        self.stdout.write(
            f'Web scrape plan: inspect {len(variants)} variants (offset {offset}, minimum score {minimum_score:.2f}).'
        )
        if not apply:
            return

        session = requests.Session()
        session.headers.update({
            'User-Agent': os.getenv(
                'CATALOG_IMAGE_USER_AGENT', 'AvaPharmacyCatalog/1.0 (info@avapharmacy.co.ke)'
            ),
            'Accept': 'image/avif,image/webp,image/png,image/jpeg,*/*;q=0.5',
        })
        matched = skipped = failed = 0
        promoted_products: dict[int, Variant] = {}

        for index, variant in enumerate(variants):
            query_name = self._variant_search_name(variant)
            if len(normalized_match_tokens(query_name)) < 2:
                skipped += 1
                self._mark_checked(variant)
                continue
            try:
                result = self._find_strict_web_result(
                    query_name,
                    normalized_barcode(variant.barcode or variant.product.barcode),
                    minimum_score,
                )
                if result is None:
                    skipped += 1
                    self._mark_checked(variant)
                else:
                    rel_path = self._download_web_packshot(session, variant, result['image'])
                    variant.image = rel_path
                    variant.image_source = IMAGE_SOURCE_WEB_SCRAPE
                    variant.image_source_url = result['image']
                    variant.image_source_page_url = result['url']
                    variant.image_verified = False
                    variant.image_checked_at = timezone.now()
                    variant.save(update_fields=(
                        'image', 'image_source', 'image_source_url', 'image_source_page_url',
                        'image_verified', 'image_checked_at', 'updated_at',
                    ))
                    promoted_products.setdefault(variant.product_id, variant)
                    matched += 1
                    self.stdout.write(
                        f'  MATCH {variant.pk}: {query_name} ({result["score"]:.2f}) ← {result["url"]}'
                    )
            except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
                failed += 1
                self.stderr.write(f'  FAIL {variant.pk}: {exc}')
            if index + 1 < len(variants):
                time.sleep(request_delay)

        for variant in promoted_products.values():
            product = variant.product
            if force or product.image_source in {IMAGE_SOURCE_MISSING, IMAGE_SOURCE_PLACEHOLDER}:
                product.image = variant.image.name
                product.image_source = IMAGE_SOURCE_WEB_SCRAPE
                product.image_source_url = variant.image_source_url
                product.image_source_page_url = variant.image_source_page_url
                product.image_verified = False
                product.image_checked_at = variant.image_checked_at
                product.save(update_fields=(
                    'image', 'image_source', 'image_source_url', 'image_source_page_url',
                    'image_verified', 'image_checked_at', 'updated_at',
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Web scrape batch complete: {matched} matched, {skipped} below threshold, {failed} failed.'
        ))

    @staticmethod
    def _variant_search_name(variant: Variant) -> str:
        product_name = re.sub(r'\*?DISCOD\*?', ' ', variant.product.name, flags=re.IGNORECASE)
        variant_name = re.sub(r'\*?DISCOD\*?', ' ', variant.name, flags=re.IGNORECASE)
        product_tokens = set(normalized_match_tokens(product_name))
        extra_tokens = [token for token in normalized_match_tokens(variant_name) if token not in product_tokens]
        combined = f'{product_name} {" ".join(extra_tokens)}'
        return re.sub(r'\s+', ' ', combined).strip(' @*')

    @staticmethod
    def _find_strict_web_result(query_name: str, barcode: str, minimum_score: float):
        from ddgs import DDGS
        from ddgs.exceptions import DDGSException

        query = f'{query_name} {barcode} product packshot'.strip()
        try:
            with DDGS() as ddgs:
                results = list(ddgs.images(
                    query,
                    region='wt-wt', safesearch='moderate', size='Large',
                    type_image='photo', max_results=8,
                ))
        except DDGSException as exc:
            raise ValueError(f'image search unavailable or rate-limited: {exc}') from exc
        candidates = []
        for result in results:
            image_url = str(result.get('image') or '')
            page_url = str(result.get('url') or '')
            title = str(result.get('title') or '')
            source_host = (urlparse(page_url).hostname or '').lower()
            if not image_url or not page_url or not title:
                continue
            if any(source_host == host or source_host.endswith(f'.{host}') for host in BLOCKED_SOURCE_HOST_SUFFIXES):
                continue
            score = image_result_match_score(query_name, title)
            if score < minimum_score:
                continue
            width = int(result.get('width') or 0)
            height = int(result.get('height') or 0)
            if width and height and min(width, height) < 350:
                continue
            candidates.append({**result, 'image': image_url, 'url': page_url, 'score': score})
        return max(candidates, key=lambda item: (item['score'], int(item.get('width') or 0)), default=None)

    @staticmethod
    def _assert_public_https_url(url: str):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname:
            raise ValueError('only public HTTPS image URLs are allowed')
        try:
            addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(f'image host could not be resolved: {parsed.hostname}') from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError(f'non-public image address rejected: {ip}')

    def _download_web_packshot(self, session: requests.Session, variant: Variant, image_url: str) -> str:
        self._assert_public_https_url(image_url)
        response = session.get(image_url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        self._assert_public_https_url(response.url)
        content_type = response.headers.get('Content-Type', '').lower()
        if 'image/' not in content_type and 'octet-stream' not in content_type:
            raise ValueError(f'non-image content type rejected: {content_type!r}')
        if len(response.content) > 12 * 1024 * 1024:
            raise ValueError('image exceeds the 12 MB download limit')
        source = Image.open(BytesIO(response.content))
        source.load()
        source = ImageOps.exif_transpose(source).convert('RGB')
        if min(source.size) < 350:
            raise ValueError(f'image is too small: {source.width}x{source.height}')
        source.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (1000, 1000), 'white')
        canvas.paste(source, ((1000 - source.width) // 2, (1000 - source.height) // 2))
        identity = normalized_barcode(variant.barcode) or str(variant.pk)
        rel_path = f'products/catalog/web-{identity}.webp'
        path = Path(settings.MEDIA_ROOT) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(path, 'WEBP', quality=88, method=6)
        return rel_path
