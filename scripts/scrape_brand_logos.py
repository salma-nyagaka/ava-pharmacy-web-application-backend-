"""
Scrape brand logos from official pharmaceutical company websites
and save them to the media/brands/ directory.
"""
import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

MEDIA_BRANDS_DIR = Path(__file__).resolve().parent.parent / "media" / "brands"
MEDIA_BRANDS_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Brand definitions: name, target filename, list of candidate logo URLs to try in order
BRANDS = [
    {
        "name": "Pfizer",
        "filename": "pfizer.svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/0/00/Pfizer_logo.svg",
        ],
    },
    {
        "name": "GSK",
        "filename": "gsk.svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/7/78/GSK_logo_2022.svg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/GSK_logo_2022.svg/1200px-GSK_logo_2022.svg.png",
        ],
    },
    {
        "name": "Novartis",
        "filename": "novartis.svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/a/ab/Novartis_logo_2020.svg",
        ],
    },
    {
        "name": "AstraZeneca",
        "filename": "astrazeneca.svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/f/f7/AstraZeneca_logo.svg",
        ],
    },
    {
        "name": "Bayer",
        "filename": "bayer.svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/5/5b/Bayer_AG_logo.svg",
        ],
    },
    {
        "name": "Sanofi",
        "filename": "sanofi.svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/5/55/Sanofi_logo_2022.svg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Sanofi_logo_2022.svg/1200px-Sanofi_logo_2022.svg.png",
        ],
    },
    {
        "name": "Abbott",
        "filename": "abbott.svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/3/35/Abbott_Laboratories_logo.svg",
        ],
    },
    {
        "name": "Cipla",
        "filename": "cipla.svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/9/90/Cipla_logo.svg",
            "https://upload.wikimedia.org/wikipedia/en/9/9d/Cipla_Logo.png",
        ],
    },
    {
        "name": "Dawa Limited",
        "filename": "dawa-limited.png",
        "urls": [
            "https://dawapharmaceuticals.com/wp-content/uploads/2022/04/Dawa-Logo-2.png",
            "https://dawa.co.ke/wp-content/uploads/logo.png",
        ],
        "scrape_url": "https://dawapharmaceuticals.com",
    },
    {
        "name": "Beta Healthcare",
        "filename": "beta-healthcare.png",
        "urls": [
            "https://betahealthcare.co.ke/wp-content/uploads/2022/01/Beta-Logo.png",
        ],
        "scrape_url": "https://betahealthcare.co.ke",
    },
    {
        "name": "Cosmos Limited",
        "filename": "cosmos-limited.png",
        "urls": [],
        "scrape_url": "https://cosmoslimited.co.ke",
    },
    {
        "name": "Strides Pharma",
        "filename": "strides-pharma.png",
        "urls": [
            "https://www.stridespharma.com/images/logo.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Strides_Pharma_Science_logo.png/320px-Strides_Pharma_Science_logo.png",
        ],
        "scrape_url": "https://www.stridespharma.com",
    },
    {
        "name": "Panadol",
        "filename": "panadol.png",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Panadol_logo.svg/1200px-Panadol_logo.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/3/36/Panadol_logo.svg",
        ],
    },
]


def download_url(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 500:
            return r.content, r.headers.get("Content-Type", "")
    except Exception as e:
        print(f"    Failed {url}: {e}")
    return None, None


def scrape_logo_from_site(site_url, timeout=15):
    """Try to find a logo image on the homepage."""
    try:
        r = requests.get(site_url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None, None
        soup = BeautifulSoup(r.text, "lxml")
        # Try common logo selectors
        candidates = []
        for sel in [
            "img.logo", "img#logo", "a.logo img", ".site-logo img",
            ".navbar-brand img", "header img", ".header__logo img",
            'img[alt*="logo" i]', 'img[src*="logo" i]',
            'a[class*="logo"] img', 'div[class*="logo"] img',
        ]:
            for img in soup.select(sel):
                src = img.get("src") or img.get("data-src")
                if src:
                    candidates.append(urljoin(site_url, src))

        # Also look for SVG logos inline or linked
        for link in soup.find_all("link", rel=lambda r: r and "icon" in r):
            href = link.get("href")
            if href:
                candidates.append(urljoin(site_url, href))

        for url in candidates:
            if any(ext in url.lower() for ext in [".svg", ".png", ".jpg", ".webp"]):
                content, ct = download_url(url)
                if content:
                    return content, ct
    except Exception as e:
        print(f"    Scrape error for {site_url}: {e}")
    return None, None


def ext_from_content_type(ct, url, target_filename):
    target_ext = Path(target_filename).suffix.lower()
    if "svg" in ct or url.endswith(".svg"):
        return ".svg"
    if "png" in ct or url.endswith(".png"):
        return ".png"
    if "webp" in ct or url.endswith(".webp"):
        return ".webp"
    if "jpeg" in ct or "jpg" in ct or url.endswith((".jpg", ".jpeg")):
        return ".jpg"
    return target_ext or ".png"


def save_logo(brand, content, ct, source_url):
    target = MEDIA_BRANDS_DIR / brand["filename"]
    # Determine actual extension from content
    actual_ext = ext_from_content_type(ct, source_url, brand["filename"])
    # If target extension differs, adjust filename
    target_stem = Path(brand["filename"]).stem
    actual_filename = target_stem + actual_ext
    save_path = MEDIA_BRANDS_DIR / actual_filename
    save_path.write_bytes(content)
    print(f"  ✓ Saved {actual_filename} ({len(content):,} bytes) from {source_url}")
    return actual_filename


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    results = {}
    for brand in BRANDS:
        print(f"\n[{brand['name']}]")
        saved = None

        # Try direct URLs first
        for url in brand.get("urls", []):
            content, ct = download_url(url)
            if content:
                saved = save_logo(brand, content, ct, url)
                break

        # Fallback: scrape from site
        if not saved and brand.get("scrape_url"):
            print(f"  Trying scrape from {brand['scrape_url']}")
            content, ct = scrape_logo_from_site(brand["scrape_url"])
            if content:
                saved = save_logo(brand, content, ct, brand["scrape_url"])

        if saved:
            results[brand["name"]] = saved
        else:
            print(f"  ✗ Could not fetch logo for {brand['name']}")

        time.sleep(0.5)

    print("\n\n=== Summary ===")
    print(f"Downloaded: {len(results)}/{len(BRANDS)}")
    for name, fname in results.items():
        print(f"  {name}: media/brands/{fname}")

    # Update DB records
    print("\n=== Updating database ===")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "avapharmacy.settings.development")
    import django
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    django.setup()
    from apps.products.models import Brand as BrandModel

    name_to_file = {b["name"]: results.get(b["name"]) for b in BRANDS}
    for brand_obj in BrandModel.objects.all():
        new_file = name_to_file.get(brand_obj.name)
        if new_file:
            brand_obj.logo = f"brands/{new_file}"
            brand_obj.save(update_fields=["logo"])
            print(f"  Updated {brand_obj.name} → brands/{new_file}")


if __name__ == "__main__":
    main()
