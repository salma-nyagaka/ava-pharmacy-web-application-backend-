"""Parsing and deterministic planning for legacy phpMyAdmin product dumps.

The legacy stores export MySQL ``INSERT`` statements rather than CSV.  This
module deliberately does not execute that SQL.  It parses only inserts into
the ``products`` table and turns them into a database-independent import plan
used by :mod:`import_legacy_catalog`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence
import unicodedata

from django.utils.text import slugify


PRODUCT_SKU_PREFIX = 'LEGACY-P-'
VARIANT_SKU_PREFIX = 'LEGACY-V-'


@dataclass(frozen=True)
class StoreSpec:
    """Identity to assign to a known legacy SQL file."""

    code: str
    name: str
    city: str


KNOWN_STORE_FILES = {
    'gtc': StoreSpec(code='gtc', name='GTC Westlands', city='Nairobi'),
    'karen': StoreSpec(code='karen', name='The Hub Karen', city='Nairobi'),
    'nyali': StoreSpec(code='nyali', name='Promenade Mall Nyali', city='Mombasa'),
}


class LegacySQLParseError(ValueError):
    """Raised when a products INSERT cannot be parsed without data loss."""


class LegacyCatalogPlanError(ValueError):
    """Raised when source files cannot be mapped into one unambiguous plan."""


@dataclass(frozen=True)
class SourceRow:
    store: StoreSpec
    source_file: str
    source_index: int
    values: Mapping[str, Any]


@dataclass(frozen=True)
class ListingPlan:
    store: StoreSpec
    source_file: str
    variant_key: str
    external_product_id: str
    price: Decimal
    cost_price: Decimal | None
    minimum_price: Decimal | None
    vat_rate: Decimal | None
    status: str
    is_active: bool
    stock_quantity: int
    reorder_level: int
    raw_data: Mapping[str, Any]


@dataclass(frozen=True)
class VariantPlan:
    key: str
    name: str
    product_key: str
    product_name: str
    category_key: str | None
    category_name: str | None
    barcode: str
    description: str
    price: Decimal
    cost_price: Decimal | None
    is_active: bool
    requires_prescription: bool
    listings: tuple[ListingPlan, ...]

    @property
    def sku(self) -> str:
        return deterministic_sku(VARIANT_SKU_PREFIX, self.key, digest_length=24)


@dataclass(frozen=True)
class ProductPlan:
    key: str
    name: str
    variant_keys: tuple[str, ...]
    is_active: bool

    @property
    def sku(self) -> str:
        return deterministic_sku(PRODUCT_SKU_PREFIX, self.key, digest_length=24)

    @property
    def slug(self) -> str:
        return deterministic_slug('legacy-product', self.name, self.key, max_length=200)


@dataclass(frozen=True)
class CategoryPlan:
    key: str
    name: str

    @property
    def slug(self) -> str:
        return deterministic_slug('legacy-category', self.name, self.key, max_length=50)


@dataclass(frozen=True)
class CatalogPlan:
    stores: tuple[StoreSpec, ...]
    categories: tuple[CategoryPlan, ...]
    products: tuple[ProductPlan, ...]
    variants: tuple[VariantPlan, ...]
    source_row_count: int
    skipped_blank_names: tuple[str, ...] = field(default_factory=tuple)

    @property
    def listing_count(self) -> int:
        return sum(len(variant.listings) for variant in self.variants)


def legacy_listing_quality_flags(listing: ListingPlan) -> list[str]:
    """Return deterministic, reviewable warnings for one legacy listing."""

    rows = listing.raw_data.get('rows', [])
    flags: set[str] = set()
    if not any(_usable_barcode(row) for row in rows):
        flags.add('missing_or_invalid_barcode')
    if listing.is_active and listing.price == Decimal('0'):
        flags.add('zero_active_price')
    if any(
        (_decimal_value(row.get('price')) or Decimal('0')) >= Decimal('99999999.99')
        for row in rows
    ):
        flags.add('sentinel_price')
    if any(
        value is not None and value < 0
        for value in (_decimal_value(row.get('buying')) for row in rows)
    ):
        flags.add('negative_cost')
    if any(
        value is not None and value < 0
        for value in (_decimal_value(row.get('left_p')) for row in rows)
    ):
        flags.add('negative_stock')
    if any(
        value is not None and (value < 0 or value > 100)
        for value in (_decimal_value(row.get('vat')) for row in rows)
    ):
        flags.add('implausible_vat')

    false_like = {'', '0', 'false', 'no', '0000-00-00'}
    if any(
        normalize_legacy_text(row.get(field_name)).casefold() not in false_like
        for row in rows
        for field_name in ('promotion', 'promo', 'prom', 'start', 'end')
    ):
        flags.add('legacy_promotion_unmapped')
    if any(normalize_legacy_text(row.get('kra')) for row in rows):
        flags.add('unmapped_kra_classification')
    return sorted(flags)


_INSERT_PRODUCTS_RE = re.compile(
    r"^[ \t]*INSERT\s+(?:(?:LOW_PRIORITY|DELAYED|HIGH_PRIORITY|IGNORE)\s+)*"
    r"INTO\s+(?:`[^`]+`\s*\.\s*)?`?products`?\s*"
    r"\((?P<columns>[^)]*)\)\s*VALUES\s*",
    flags=re.IGNORECASE | re.MULTILINE,
)
_COLUMN_RE = re.compile(r"`([^`]+)`|([A-Za-z_][A-Za-z0-9_]*)")
_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_RE = re.compile(
    r"^[+-]?(?:(?:\d+\.\d*)|(?:\d*\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?$"
)
_WHITESPACE_RE = re.compile(r'\s+')


def infer_store_spec(path: str | Path) -> StoreSpec:
    """Return the explicit store mapping for a known dump filename."""

    stem = Path(path).stem.casefold()
    try:
        return KNOWN_STORE_FILES[stem]
    except KeyError as exc:
        known = ', '.join(f'{name}.sql' for name in sorted(KNOWN_STORE_FILES))
        raise LegacyCatalogPlanError(
            f'Cannot infer a store for {Path(path).name!r}; expected one of: {known}.'
        ) from exc


def normalize_legacy_text(value: Any) -> str:
    """Normalize display text without erasing meaningful punctuation."""

    if value is None:
        return ''
    normalized = unicodedata.normalize('NFKC', str(value))
    return _WHITESPACE_RE.sub(' ', normalized).strip()


def normalized_text_key(value: Any) -> str:
    """Return the exact-name grouping key used across all stores."""

    return normalize_legacy_text(value).casefold()


def deterministic_sku(prefix: str, key: str, *, digest_length: int = 24) -> str:
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()[:digest_length].upper()
    return f'{prefix}{digest}'


def deterministic_slug(
    namespace: str,
    display_name: str,
    key: str,
    *,
    max_length: int,
) -> str:
    """Build a readable slug whose uniqueness comes from stable source data."""

    digest = hashlib.sha256(f'{namespace}\0{key}'.encode('utf-8')).hexdigest()[:12]
    readable = slugify(display_name) or namespace
    readable_length = max(1, max_length - len(digest) - 1)
    readable = readable[:readable_length].rstrip('-') or namespace[:readable_length]
    return f'{readable}-{digest}'


def _decode_sql(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        # These phpMyAdmin files declare latin1.  Latin-1 is also lossless for
        # arbitrary bytes, so source values can always be retained in raw_data.
        return data.decode('latin-1')


def _line_number(text: str, position: int) -> int:
    return text.count('\n', 0, position) + 1


def _parse_unquoted_value(token: str) -> Any:
    token = token.strip()
    if not token:
        raise LegacySQLParseError('Empty unquoted SQL value.')
    if token.casefold() == 'null':
        return None
    if _INTEGER_RE.fullmatch(token):
        return int(token)
    if _DECIMAL_RE.fullmatch(token):
        return Decimal(token)
    # phpMyAdmin can emit SQL expressions in dumps.  Keeping the token is
    # safer than evaluating it, and preserves it in the listing's raw data.
    return token


def _parse_quoted_value(text: str, position: int, *, source: str) -> tuple[str, int]:
    result: list[str] = []
    length = len(text)
    position += 1  # opening quote
    mysql_escapes = {
        '0': '\0',
        'b': '\b',
        'n': '\n',
        'r': '\r',
        't': '\t',
        'Z': '\x1a',
        '\\': '\\',
        "'": "'",
        '"': '"',
    }

    while position < length:
        character = text[position]
        if character == '\\':
            if position + 1 >= length:
                raise LegacySQLParseError(f'{source}: unterminated backslash escape.')
            escaped = text[position + 1]
            result.append(mysql_escapes.get(escaped, escaped))
            position += 2
            continue
        if character == "'":
            if position + 1 < length and text[position + 1] == "'":
                result.append("'")
                position += 2
                continue
            return ''.join(result), position + 1
        result.append(character)
        position += 1

    raise LegacySQLParseError(f'{source}: unterminated quoted SQL value.')


def _parse_values_clause(
    text: str,
    position: int,
    *,
    columns: Sequence[str],
    source: str,
) -> Iterator[dict[str, Any]]:
    length = len(text)

    while position < length:
        while position < length and text[position].isspace():
            position += 1
        if position < length and text[position] == ';':
            return
        if position >= length or text[position] != '(':
            line = _line_number(text, position)
            found = text[position:position + 30].splitlines()[0] if position < length else 'EOF'
            raise LegacySQLParseError(
                f'{source}:{line}: expected a values tuple, found {found!r}.'
            )

        position += 1
        values: list[Any] = []
        while True:
            while position < length and text[position].isspace():
                position += 1
            if position >= length:
                raise LegacySQLParseError(f'{source}: unterminated values tuple.')

            if text[position] == "'":
                value, position = _parse_quoted_value(text, position, source=source)
            else:
                start = position
                while position < length and text[position] not in ',)':
                    position += 1
                value = _parse_unquoted_value(text[start:position])
            values.append(value)

            while position < length and text[position].isspace():
                position += 1
            if position >= length:
                raise LegacySQLParseError(f'{source}: unterminated values tuple.')
            if text[position] == ',':
                position += 1
                continue
            if text[position] == ')':
                position += 1
                break
            line = _line_number(text, position)
            raise LegacySQLParseError(
                f'{source}:{line}: expected a comma or closing parenthesis.'
            )

        if len(values) != len(columns):
            line = _line_number(text, position)
            raise LegacySQLParseError(
                f'{source}:{line}: products row has {len(values)} values for '
                f'{len(columns)} columns.'
            )
        yield dict(zip(columns, values))

        while position < length and text[position].isspace():
            position += 1
        if position < length and text[position] == ',':
            position += 1
            continue
        if position < length and text[position] == ';':
            return
        line = _line_number(text, position)
        found = text[position:position + 30].splitlines()[0] if position < length else 'EOF'
        raise LegacySQLParseError(
            f'{source}:{line}: expected a comma or semicolon after a tuple, found {found!r}.'
        )

    raise LegacySQLParseError(f'{source}: products INSERT ended without a semicolon.')


def iter_product_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield products rows from a phpMyAdmin MySQL dump.

    MySQL's doubled quotes and backslash escapes are both supported.  Other
    tables and all DDL are ignored; no SQL is ever evaluated or executed.
    """

    source_path = Path(path)
    text = _decode_sql(source_path)
    for match in _INSERT_PRODUCTS_RE.finditer(text):
        columns = [left or right for left, right in _COLUMN_RE.findall(match.group('columns'))]
        if not columns:
            line = _line_number(text, match.start())
            raise LegacySQLParseError(
                f'{source_path}:{line}: products INSERT has no columns.'
            )
        yield from _parse_values_clause(
            text,
            match.end(),
            columns=columns,
            source=str(source_path),
        )


def _mode_sort_key(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
        return (0, Decimal(value))
    text = str(value)
    return (1, normalized_text_key(text), text)


def deterministic_mode(values: Iterable[Any], *, default: Any = None) -> Any:
    """Return a stable statistical mode, choosing the lowest stable tie."""

    counts = Counter(value for value in values if value is not None)
    if not counts:
        return default
    highest_count = max(counts.values())
    candidates = [value for value, count in counts.items() if count == highest_count]
    return min(candidates, key=_mode_sort_key)


def canonical_text(values: Iterable[Any], *, default: str = '') -> str:
    """Choose display text by normalized key, retaining a real source value."""

    displays_by_key: dict[str, list[str]] = defaultdict(list)
    for value in values:
        display = normalize_legacy_text(value)
        if display:
            displays_by_key[normalized_text_key(display)].append(display)
    if not displays_by_key:
        return default

    winning_key = deterministic_mode(
        key for key, displays in displays_by_key.items() for _ in displays
    )
    return deterministic_mode(displays_by_key[winning_key], default=default)


def _decimal_value(value: Any) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    return decimal_value if decimal_value.is_finite() else None


def _nonnegative_decimal_value(value: Any) -> Decimal | None:
    decimal_value = _decimal_value(value)
    if decimal_value is None or decimal_value < 0:
        return None
    return decimal_value


def _nonnegative_int(value: Any) -> int:
    decimal_value = _decimal_value(value)
    if decimal_value is None or decimal_value <= 0:
        return 0
    return int(decimal_value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _is_active_status(value: Any) -> bool:
    return normalized_text_key(value) in {'active', 'enabled', 'yes', 'true', '1'}


def _usable_barcode(row: Mapping[str, Any]) -> str:
    value = normalize_legacy_text(row.get('code'))
    if not re.fullmatch(r'\d{8,14}', value):
        return ''
    if len(set(value)) == 1:
        return ''
    return value


def _row_sort_key(source_row: SourceRow) -> tuple[Any, ...]:
    product_id = source_row.values.get('product_id')
    try:
        numeric_id = int(product_id)
    except (TypeError, ValueError):
        numeric_id = 2**63 - 1
    return (numeric_id, source_row.source_index)


def _split_variant_slots(
    variant_key: str,
    source_rows: Sequence[SourceRow],
) -> tuple[tuple[str, tuple[SourceRow, ...]], ...]:
    """Split equal-name rows into slots containing at most one row per store.

    A repeated name inside one store cannot share a ``StoreVariantListing`` due
    to the store/variant uniqueness constraint.  Match rows with the same
    plausible barcode first, then place every remaining row by deterministic
    store-local ordinal.  The latter is deliberately only a fallback because
    the legacy dumps do not contain a canonical cross-store product key.
    """

    rows_by_store: dict[str, list[SourceRow]] = defaultdict(list)
    for source_row in source_rows:
        rows_by_store[source_row.store.code].append(source_row)
    for store_rows in rows_by_store.values():
        store_rows.sort(key=_row_sort_key)

    barcode_rows: dict[str, dict[str, list[SourceRow]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for store_code, store_rows in rows_by_store.items():
        for source_row in store_rows:
            barcode = _usable_barcode(source_row.values)
            if barcode:
                barcode_rows[barcode][store_code].append(source_row)

    slots: list[tuple[str, dict[str, SourceRow]]] = []
    assigned_rows: set[tuple[str, int]] = set()
    for barcode in sorted(barcode_rows):
        matches_by_store = barcode_rows[barcode]
        occurrence_count = max(len(rows) for rows in matches_by_store.values())
        for occurrence in range(occurrence_count):
            matches = {
                store_code: store_rows[occurrence]
                for store_code, store_rows in sorted(matches_by_store.items())
                if occurrence < len(store_rows)
            }
            # A barcode seen in only one store provides no cross-store match;
            # leave that row for the deterministic ordinal fallback instead.
            if len(matches) < 2:
                continue
            slots.append((f'barcode:{barcode}:{occurrence + 1}', matches))
            assigned_rows.update(
                (source_row.store.code, source_row.source_index)
                for source_row in matches.values()
            )

    ordinal_number = 0
    for store_code in sorted(rows_by_store):
        remaining_rows = [
            source_row
            for source_row in rows_by_store[store_code]
            if (store_code, source_row.source_index) not in assigned_rows
        ]
        available_slot_indexes = [
            index
            for index, (_, slot_rows) in enumerate(slots)
            if store_code not in slot_rows
        ]
        for source_row, slot_index in zip(remaining_rows, available_slot_indexes):
            slots[slot_index][1][store_code] = source_row
            assigned_rows.add((store_code, source_row.source_index))

        for source_row in remaining_rows[len(available_slot_indexes):]:
            ordinal_number += 1
            slots.append((f'ordinal:{ordinal_number}', {store_code: source_row}))
            assigned_rows.add((store_code, source_row.source_index))

    if sum(len(slot_rows) for _, slot_rows in slots) != len(source_rows):
        raise LegacyCatalogPlanError(
            f'Internal error while splitting duplicate variant name {variant_key!r}.'
        )

    single_slot = len(slots) == 1
    return tuple(
        (
            variant_key if single_slot else f'{variant_key}\x1f{slot_label}',
            tuple(slot_rows[store_code] for store_code in sorted(slot_rows)),
        )
        for slot_label, slot_rows in slots
    )


def _build_listing_plan(
    store: StoreSpec,
    variant_key: str,
    source_rows: Sequence[SourceRow],
) -> ListingPlan:
    ordered_rows = sorted(source_rows, key=_row_sort_key)
    representative = ordered_rows[0]
    price = deterministic_mode(
        (_decimal_value(source.values.get('price')) for source in ordered_rows),
        default=Decimal('0.00'),
    )
    status = canonical_text((source.values.get('status') for source in ordered_rows))
    source_file = representative.source_file
    return ListingPlan(
        store=store,
        source_file=source_file,
        variant_key=variant_key,
        external_product_id=normalize_legacy_text(representative.values.get('product_id'))[:80],
        price=price,
        cost_price=deterministic_mode(
            _nonnegative_decimal_value(source.values.get('buying'))
            for source in ordered_rows
        ),
        minimum_price=deterministic_mode(
            _decimal_value(source.values.get('minimum')) for source in ordered_rows
        ),
        vat_rate=deterministic_mode(
            _decimal_value(source.values.get('vat')) for source in ordered_rows
        ),
        status=status,
        is_active=any(_is_active_status(source.values.get('status')) for source in ordered_rows),
        stock_quantity=sum(_nonnegative_int(source.values.get('left_p')) for source in ordered_rows),
        reorder_level=sum(_nonnegative_int(source.values.get('reorder')) for source in ordered_rows),
        raw_data={
            'source_file': source_file,
            'store_code': store.code,
            'source_row_count': len(ordered_rows),
            # Always use a list so duplicate legacy rows are never collapsed or
            # overwritten, even when their product_id values also collide.
            'rows': [_json_safe(source.values) for source in ordered_rows],
        },
    )


def build_catalog_plan(
    sources: Iterable[tuple[StoreSpec, str, Iterable[Mapping[str, Any]]]],
    *,
    product_name_normalizer: Callable[[str], str],
) -> CatalogPlan:
    """Aggregate parsed store rows into products, variants, and listings."""

    rows_by_variant: dict[str, list[SourceRow]] = defaultdict(list)
    skipped_blank_names: list[str] = []
    stores_by_code: dict[str, StoreSpec] = {}
    source_row_count = 0

    for store, source_file, rows in sources:
        existing_store = stores_by_code.get(store.code)
        if existing_store is not None:
            raise LegacyCatalogPlanError(
                f'More than one input file maps to store {store.code!r}.'
            )
        stores_by_code[store.code] = store
        store_source_row_count = 0
        for source_index, row in enumerate(rows, start=1):
            store_source_row_count += 1
            source_row_count += 1
            name = normalize_legacy_text(row.get('p_name'))
            if not name:
                product_id = normalize_legacy_text(row.get('product_id')) or '?'
                skipped_blank_names.append(f'{source_file} product_id={product_id}')
                continue
            rows_by_variant[normalized_text_key(name)].append(
                SourceRow(
                    store=store,
                    source_file=source_file,
                    source_index=source_index,
                    values=dict(row),
                )
            )
        if store_source_row_count == 0:
            raise LegacyCatalogPlanError(
                f'Legacy SQL file {source_file!r} contains no products rows for '
                f'store {store.code!r}.'
            )

    variant_plans: list[VariantPlan] = []
    categories_by_key: dict[str, str] = {}
    product_variant_keys: dict[str, list[str]] = defaultdict(list)
    product_names: dict[str, list[str]] = defaultdict(list)

    for base_variant_key in sorted(rows_by_variant):
        for variant_key, slot_source_rows in _split_variant_slots(
            base_variant_key,
            rows_by_variant[base_variant_key],
        ):
            source_rows = list(slot_source_rows)
            name = canonical_text(source.values.get('p_name') for source in source_rows)
            product_name = normalize_legacy_text(product_name_normalizer(name)) or name
            product_key = normalized_text_key(product_name)
            category_name = canonical_text(source.values.get('category') for source in source_rows)
            category_key = normalized_text_key(category_name) or None
            if category_key:
                categories_by_key.setdefault(category_key, category_name)

            listings_by_store: dict[str, list[SourceRow]] = defaultdict(list)
            for source in source_rows:
                listings_by_store[source.store.code].append(source)
            listings = tuple(
                _build_listing_plan(
                    stores_by_code[store_code],
                    variant_key,
                    listings_by_store[store_code],
                )
                for store_code in sorted(listings_by_store)
            )

            description = canonical_text(source.values.get('description') for source in source_rows)
            usable_barcodes = [
                barcode
                for barcode in (_usable_barcode(source.values) for source in source_rows)
                if barcode
            ]
            variant_plans.append(
                VariantPlan(
                    key=variant_key,
                    name=name,
                    product_key=product_key,
                    product_name=product_name,
                    category_key=category_key,
                    category_name=category_name or None,
                    barcode=deterministic_mode(usable_barcodes, default=''),
                    description=description,
                    price=deterministic_mode(
                        (_decimal_value(source.values.get('price')) for source in source_rows),
                        default=Decimal('0.00'),
                    ),
                    cost_price=deterministic_mode(
                        _nonnegative_decimal_value(source.values.get('buying'))
                        for source in source_rows
                    ),
                    is_active=any(listing.is_active for listing in listings),
                    requires_prescription=any(
                        normalized_text_key(source.values.get('category'))
                        == normalized_text_key('DISPENSARY')
                        for source in source_rows
                    ),
                    listings=listings,
                )
            )
            product_variant_keys[product_key].append(variant_key)
            product_names[product_key].append(product_name)

    variants_by_key = {variant.key: variant for variant in variant_plans}
    product_plans = tuple(
        ProductPlan(
            key=product_key,
            name=canonical_text(product_names[product_key]),
            variant_keys=tuple(sorted(product_variant_keys[product_key])),
            is_active=any(
                variants_by_key[variant_key].is_active
                for variant_key in product_variant_keys[product_key]
            ),
        )
        for product_key in sorted(product_variant_keys)
    )
    category_plans = tuple(
        CategoryPlan(key=key, name=categories_by_key[key])
        for key in sorted(categories_by_key)
    )

    return CatalogPlan(
        stores=tuple(stores_by_code[code] for code in sorted(stores_by_code)),
        categories=category_plans,
        products=product_plans,
        variants=tuple(variant_plans),
        source_row_count=source_row_count,
        skipped_blank_names=tuple(skipped_blank_names),
    )


def load_catalog_plan(
    sql_files: Iterable[str | Path],
    *,
    product_name_normalizer: Callable[[str], str],
) -> CatalogPlan:
    """Parse known dump files and return their combined catalog plan."""

    mapped_files: list[tuple[StoreSpec, Path]] = []
    seen_store_codes: set[str] = set()
    for value in sql_files:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise LegacyCatalogPlanError(f'Legacy SQL file does not exist: {path}')
        store = infer_store_spec(path)
        if store.code in seen_store_codes:
            raise LegacyCatalogPlanError(
                f'More than one input file maps to store {store.code!r}.'
            )
        seen_store_codes.add(store.code)
        mapped_files.append((store, path))

    missing_store_codes = sorted(set(KNOWN_STORE_FILES) - seen_store_codes)
    if missing_store_codes:
        missing_files = ', '.join(f'{code}.sql' for code in missing_store_codes)
        raise LegacyCatalogPlanError(
            'A complete catalog import requires all three known store dumps; '
            f'missing: {missing_files}.'
        )

    return build_catalog_plan(
        (
            (store, path.name, iter_product_rows(path))
            for store, path in sorted(mapped_files, key=lambda item: item[0].code)
        ),
        product_name_normalizer=product_name_normalizer,
    )
