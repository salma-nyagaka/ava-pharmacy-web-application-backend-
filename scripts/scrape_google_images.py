"""
Scrape product images using Google Images and Bing Images.
"""
import re
import json
import time
import random
import requests
from pathlib import Path
from urllib.parse import quote_plus, urlencode

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_PRODUCTS_DIR = BASE_DIR / "media" / "products"

HEADERS_GOOGLE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

HEADERS_IMG = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

REMAINING = [
    ("dettol-antiseptic-liquid-250ml.jpg",                    "Dettol antiseptic liquid 250ml bottle"),
    ("johnsons-baby-lotion-200ml.jpg",                        "Johnson Baby Lotion 200ml"),
    ("strepsils-honey-lemon-lozenges-24s.jpg",                "Strepsils honey lemon 24 lozenges pack"),
    ("sudocrem-antiseptic-healing-cream-125g.jpg",            "Sudocrem healing cream 125g"),
    ("eucerin-sun-fluid-spf-50-50ml.jpg",                     "Eucerin sun fluid SPF 50 tube"),
    ("omron-m2-upper-arm-blood-pressure-monitor.jpg",         "Omron M2 blood pressure monitor"),
    ("pregnacare-plus-2828-tablets.jpg",                      "Pregnacare Plus 56 tablets pregnancy"),
    ("vitamin-c-1000mg-effervescent-tablets-20s.jpg",         "vitamin C 1000mg effervescent tablets 20"),
    ("ferrous-sulphate-folic-acid-200mg04mg-tablets-30s.jpg", "ferrous sulphate folic acid iron tablets pharmacy"),
    ("moringa-leaf-powder-200g.jpg",                          "organic moringa leaf powder 200g pouch"),
    ("omeprazole-20mg-capsules.jpg",                          "omeprazole 20mg capsules pharmacy pack"),
    ("amoxicillin-500mg-capsules.jpg",                        "amoxicillin 500mg capsules antibiotic pack"),
    ("co-amoxiclav-625mg-tablets.jpg",                        "co-amoxiclav 625mg Augmentin tablets"),
    ("salbutamol-inhaler-100mcg.jpg",                         "salbutamol Ventolin blue inhaler 100mcg"),
    ("metformin-500mg-tablets.jpg",                           "metformin 500mg tablets Glucophage"),
    ("glibenclamide-5mg-tablets.jpg",                         "glibenclamide 5mg tablets blister"),
    ("amlodipine-5mg-tablets.jpg",                            "amlodipine 5mg tablets blood pressure"),
    ("losartan-50mg-tablets.jpg",                             "losartan potassium 50mg tablets"),
    ("artemetherlumefantrine-20120mg-tablets-al.jpg",         "Coartem artemether lumefantrine tablets malaria"),
]


def extract_image_urls_from_google(html):
    """Extract image URLs from Google Images HTML."""
    urls = []
    # Pattern 1: JSON data with ou (original URL) field
    for match in re.finditer(r'"ou":"(https?://[^"]+)"', html):
        url = match.group(1).replace("\\u003d", "=").replace("\\u0026", "&")
        urls.append(url)
    # Pattern 2: data-src attributes
    for match in re.finditer(r'data-src="(https?://[^"]+(?:jpg|jpeg|png|webp)[^"]*)"', html, re.IGNORECASE):
        urls.append(match.group(1))
    return urls


def extract_image_urls_from_bing(html):
    """Extract image URLs from Bing Images HTML."""
    urls = []
    for match in re.finditer(r'"murl":"(https?://[^"]+)"', html):
        urls.append(match.group(1))
    for match in re.finditer(r'imgurl:([^\s&,]+)', html):
        url = match.group(1)
        if url.startswith("http"):
            urls.append(url)
    return urls


def try_download(url, min_size=5000):
    try:
        r = requests.get(url, headers=HEADERS_IMG, timeout=10, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        if (r.status_code == 200
                and any(t in ct for t in ["image/", "jpeg", "png", "webp"])
                and len(r.content) > min_size):
            return r.content
    except Exception:
        pass
    return None


def search_google_images(query):
    url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch&tbs=isz:m"
    try:
        r = requests.get(url, headers=HEADERS_GOOGLE, timeout=15)
        if r.status_code == 200:
            return extract_image_urls_from_google(r.text)
    except Exception as e:
        print(f"    Google error: {e}")
    return []


def search_bing_images(query):
    url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC2&first=1&tsc=ImageBasicHover"
    try:
        r = requests.get(url, headers=HEADERS_GOOGLE, timeout=15)
        if r.status_code == 200:
            return extract_image_urls_from_bing(r.text)
    except Exception as e:
        print(f"    Bing error: {e}")
    return []


skip_domains = [
    "wikimedia", "wikipedia", "pinterest", "instagram",
    "facebook", "twitter", "tiktok", "reddit", "alamy",
    "shutterstock", "gettyimages", "istockphoto", "dreamstime",
    "123rf", "depositphotos",
]


def find_image(query):
    # Try Bing first (usually more permissive)
    urls = search_bing_images(query)
    if not urls:
        time.sleep(2)
        urls = search_google_images(query)

    for url in urls[:20]:
        if any(d in url.lower() for d in skip_domains):
            continue
        content = try_download(url)
        if content:
            return content, url
    return None, None


success = 0
failed = []

for filename, query in REMAINING:
    save_path = MEDIA_PRODUCTS_DIR / filename
    print(f"\n[{filename}]")

    content, url = find_image(query)
    if content:
        save_path.write_bytes(content)
        print(f"  ✓ {len(content):,}b from {url[:80]}")
        success += 1
    else:
        print(f"  ✗ Not found")
        failed.append(filename)

    time.sleep(random.uniform(3, 5))

print(f"\n=== Done: {success}/{len(REMAINING)} ===")
if failed:
    print("Failed:")
    for f in failed:
        print(f"  {f}")
