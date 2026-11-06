"""Populate brand logos from verified Wikidata brand entities.

The command deliberately avoids generic image search.  It accepts only an
exact brand-label match whose Wikidata description looks like a brand or
company, then uses either the entity's Commons logo (P154) or the favicon for
its claimed official website (P856).
"""

from __future__ import annotations

import os
import re
import time
from hashlib import sha256
from io import BytesIO
from urllib.parse import quote, unquote, urlparse

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from apps.products.models import Brand


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
FAVICON_URL = "https://www.google.com/s2/favicons?domain={domain}&sz=256"
USER_AGENT = "AvaPharmacyCatalog/1.0 (brand logo curation)"

GOOD_DESCRIPTION_WORDS = {
    "brand", "company", "manufacturer", "corporation", "business",
    "consumer goods", "product", "products", "fashion house",
}
STRONG_DESCRIPTION_WORDS = {
    "cosmetics", "skincare", "skin care", "personal care", "healthcare",
    "pharmaceutical", "nutrition", "supplement", "medical", "toiletries",
    "hygiene", "beauty", "medicine", "vitamin", "oral care", "baby care",
}
BAD_DESCRIPTION_WORDS = {
    "given name", "surname", "singer", "actor", "actress", "album",
    "song", "film", "television series", "village", "river", "disambiguation",
    "footballer", "politician", "fictional character",
}

# Exact-label entities whose media is known not to represent the catalogue
# brand (for example, EOS Imaging rather than the lip-care brand EOS).
DISALLOWED_ENTITY_IDS_BY_BRAND = {
    "burtsbees": {"Q5000673"},
    "eos": {"Q3046037"},
    "elastoplast": {"Q911211"},
}


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _entity_score(brand_name: str, candidate: dict) -> int:
    label = candidate.get("label") or ""
    if _normalise(label) != _normalise(brand_name):
        return -100

    description = (candidate.get("description") or "").casefold()
    if any(word in description for word in BAD_DESCRIPTION_WORDS):
        return -100

    score = 60
    if any(word in description for word in GOOD_DESCRIPTION_WORDS):
        score += 20
    if any(word in description for word in STRONG_DESCRIPTION_WORDS):
        score += 45
    if candidate.get("match", {}).get("type") == "label":
        score += 10
    return score


def _claim_values(claims: dict, property_id: str) -> list[str]:
    values = []
    statements = sorted(
        claims.get(property_id, []),
        key=lambda item: item.get("rank") == "preferred",
        reverse=True,
    )
    for statement in statements:
        snak = statement.get("mainsnak", {})
        value = snak.get("datavalue", {}).get("value")
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return values


class Command(BaseCommand):
    help = "Attach verified Wikidata/Commons logos to imported brand records."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist downloaded logos.")
        parser.add_argument("--force", action="store_true", help="Replace existing logo files.")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--offset", type=int, default=0)
        parser.add_argument("--delay", type=float, default=0.15)
        parser.add_argument(
            "--generate-fallbacks",
            action="store_true",
            help="Create local typographic wordmarks when no verified web logo is available.",
        )

    def handle(self, *args, **options):
        if options["offset"] < 0:
            raise CommandError("--offset must be zero or greater")
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be greater than zero")

        queryset = Brand.objects.order_by("name", "pk")
        if not options["force"]:
            queryset = queryset.filter(logo="")
        end = None if options["limit"] is None else options["offset"] + options["limit"]
        brands = list(queryset[options["offset"]:end])

        mode = "apply" if options["apply"] else "preview"
        self.stdout.write(f"Brand logo {mode}: inspecting {len(brands)} brands.")
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        entity_matches = self._bulk_entity_matches(session, [brand.name for brand in brands])

        matched = fallback_count = skipped = failed = 0
        for brand in brands:
            try:
                match = self._resolve_known_entity(
                    session,
                    entity_matches.get(_normalise(brand.name)),
                )
                if not match:
                    if options["apply"] and options["generate_fallbacks"]:
                        self._save_fallback(brand)
                        self.stdout.write(f"  FALLBACK {brand.name}: generated local wordmark")
                        fallback_count += 1
                        continue
                    self.stdout.write(self.style.WARNING(f"  SKIP {brand.name}: no verified logo source"))
                    skipped += 1
                    continue
                image_bytes, entity_id, source_url = match
                if options["apply"]:
                    brand.logo.save(
                        f"{brand.slug}.png",
                        ContentFile(image_bytes),
                        save=False,
                    )
                    brand.save(update_fields=["logo", "updated_at"])
                self.stdout.write(self.style.SUCCESS(
                    f"  MATCH {brand.name}: {entity_id} <- {source_url}"
                ))
                matched += 1
            except (requests.RequestException, ValueError, UnidentifiedImageError) as exc:
                if options["apply"] and options["generate_fallbacks"]:
                    self._save_fallback(brand)
                    self.stdout.write(f"  FALLBACK {brand.name}: source failed; generated local wordmark")
                    fallback_count += 1
                    continue
                self.stdout.write(self.style.WARNING(f"  FAIL {brand.name}: {exc}"))
                failed += 1
            time.sleep(max(options["delay"], 0))

        self.stdout.write(self.style.SUCCESS(
            f"Brand logo {mode} complete: {matched} verified, {fallback_count} generated, "
            f"{skipped} unmatched, {failed} failed."
        ))

    def _save_fallback(self, brand: Brand) -> None:
        brand.logo.save(
            f"generated/{brand.slug}.png",
            ContentFile(self._generate_wordmark(brand.name)),
            save=False,
        )
        brand.save(update_fields=["logo", "updated_at"])

    def _generate_wordmark(self, brand_name: str) -> bytes:
        palette = [
            (20, 82, 120), (14, 116, 109), (109, 40, 217), (190, 24, 93),
            (194, 65, 12), (29, 78, 216), (67, 56, 202), (21, 128, 61),
        ]
        accent = palette[sha256(brand_name.encode("utf-8")).digest()[0] % len(palette)]
        canvas = Image.new("RGB", (512, 512), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((18, 18, 494, 494), radius=72, fill=(248, 250, 252), outline=accent, width=10)
        draw.rounded_rectangle((58, 68, 454, 80), radius=6, fill=accent)

        font_paths = (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        )
        font_path = next((path for path in font_paths if os.path.isfile(path)), None)
        words = brand_name.split()
        lines = [brand_name]
        if len(brand_name) > 17 and len(words) > 1:
            split_at = min(range(1, len(words)), key=lambda index: abs(
                len(" ".join(words[:index])) - len(" ".join(words[index:]))
            ))
            lines = [" ".join(words[:split_at]), " ".join(words[split_at:])]

        font_size = 88 if len(lines) == 1 else 70
        while font_size >= 34:
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
            widths = [draw.textbbox((0, 0), line, font=font)[2] for line in lines]
            if max(widths) <= 400:
                break
            font_size -= 4

        line_height = font_size + 14
        top = (512 - (line_height * len(lines))) // 2
        for index, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            width = bbox[2] - bbox[0]
            draw.text(((512 - width) // 2, top + index * line_height), line, fill=accent, font=font)

        output = BytesIO()
        canvas.save(output, format="PNG", optimize=True)
        return output.getvalue()

    def _bulk_entity_matches(self, session: requests.Session, brand_names: list[str]) -> dict:
        if not brand_names:
            return {}
        values = " ".join(
            f'"{name.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"@en'
            for name in brand_names
        )
        query = f"""
            SELECT ?brand ?brandLabel ?brandDescription ?logo ?website WHERE {{
              VALUES ?brandLabel {{ {values} }}
              ?brand rdfs:label ?brandLabel.
              OPTIONAL {{ ?brand wdt:P154 ?logo. }}
              OPTIONAL {{ ?brand wdt:P856 ?website. }}
              SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "en".
                ?brand schema:description ?brandDescription.
              }}
            }}
        """
        payload = self._request_json(
            session,
            WIKIDATA_SPARQL,
            params={"query": query, "format": "json"},
        )
        entities = {}
        for binding in payload.get("results", {}).get("bindings", []):
            label = binding.get("brandLabel", {}).get("value", "")
            entity_url = binding.get("brand", {}).get("value", "")
            entity_id = entity_url.rsplit("/", 1)[-1]
            if not label or not entity_id:
                continue
            key = (_normalise(label), entity_id)
            entry = entities.setdefault(key, {
                "id": entity_id,
                "label": label,
                "description": binding.get("brandDescription", {}).get("value", ""),
                "match": {"type": "label"},
                "logos": [],
                "websites": [],
            })
            logo = binding.get("logo", {}).get("value")
            website = binding.get("website", {}).get("value")
            if logo and logo not in entry["logos"]:
                entry["logos"].append(logo)
            if website and website not in entry["websites"]:
                entry["websites"].append(website)

        matches = {}
        for brand_name in brand_names:
            normalised = _normalise(brand_name)
            candidates = [
                value for (label_key, _), value in entities.items()
                if label_key == normalised
                and value["id"] not in DISALLOWED_ENTITY_IDS_BY_BRAND.get(normalised, set())
            ]
            candidates.sort(key=lambda item: _entity_score(brand_name, item), reverse=True)
            if candidates and _entity_score(brand_name, candidates[0]) >= 90:
                matches[normalised] = candidates[0]
        return matches

    def _resolve_known_entity(self, session: requests.Session, entity: dict | None):
        if not entity:
            return None
        entity_id = entity["id"]

        for logo_url in entity.get("logos", []):
            filename = unquote(urlparse(logo_url).path.rsplit("/", 1)[-1])
            source_url = self._commons_thumbnail_url(session, filename)
            if source_url:
                image_bytes = self._download_and_normalise(session, source_url)
                if image_bytes:
                    return image_bytes, entity_id, source_url

        # Only accept an official-site icon when the domain itself contains
        # the brand name. This rejects parent-company and unrelated-site icons.
        brand_key = _normalise(entity.get("label", ""))
        for website in entity.get("websites", []):
            domain = urlparse(website).hostname
            if not domain or brand_key not in _normalise(domain):
                continue
            source_url = FAVICON_URL.format(domain=quote(domain, safe="."))
            image_bytes = self._download_and_normalise(session, source_url)
            if image_bytes:
                return image_bytes, entity_id, source_url
        return None

    def _request_json(self, session: requests.Session, url: str, *, params=None) -> dict:
        response = session.get(url, params=params, timeout=15)
        if response.status_code == 429:
            time.sleep(min(float(response.headers.get("Retry-After", 2)), 10))
            response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def _resolve_logo(self, session: requests.Session, brand_name: str):
        search = self._request_json(session, WIKIDATA_API, params={
            "action": "wbsearchentities",
            "search": brand_name,
            "language": "en",
            "type": "item",
            "limit": 8,
            "format": "json",
            "origin": "*",
        })
        candidates = sorted(
            search.get("search", []),
            key=lambda item: _entity_score(brand_name, item),
            reverse=True,
        )
        if not candidates or _entity_score(brand_name, candidates[0]) < 90:
            return None

        entity_id = candidates[0]["id"]
        entity_payload = self._request_json(
            session,
            WIKIDATA_ENTITY.format(entity_id=entity_id),
        )
        claims = entity_payload["entities"][entity_id].get("claims", {})

        for commons_filename in _claim_values(claims, "P154"):
            source_url = self._commons_thumbnail_url(session, commons_filename)
            if source_url:
                image_bytes = self._download_and_normalise(session, source_url)
                if image_bytes:
                    return image_bytes, entity_id, source_url

        for website in _claim_values(claims, "P856"):
            domain = urlparse(website).hostname
            if not domain:
                continue
            source_url = FAVICON_URL.format(domain=quote(domain, safe="."))
            image_bytes = self._download_and_normalise(session, source_url)
            if image_bytes:
                return image_bytes, entity_id, source_url
        return None

    def _commons_thumbnail_url(self, session: requests.Session, filename: str) -> str | None:
        payload = self._request_json(session, COMMONS_API, params={
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 512,
            "titles": f"File:{filename}",
            "origin": "*",
        })
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            info = page.get("imageinfo", [])
            if info:
                return info[0].get("thumburl") or info[0].get("url")
        return None

    def _download_and_normalise(self, session: requests.Session, url: str) -> bytes | None:
        response = session.get(url, timeout=20)
        if response.status_code != 200:
            return None
        if "image" not in response.headers.get("Content-Type", "").casefold():
            return None
        if len(response.content) > 5 * 1024 * 1024:
            return None

        with Image.open(BytesIO(response.content)) as source:
            source.load()
            if min(source.size) < 32:
                return None
            logo = source.convert("RGBA")
            logo.thumbnail((440, 440), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
            position = ((512 - logo.width) // 2, (512 - logo.height) // 2)
            canvas.alpha_composite(logo, position)
            canvas = ImageOps.exif_transpose(canvas)
            output = BytesIO()
            canvas.save(output, format="PNG", optimize=True)
            return output.getvalue()
