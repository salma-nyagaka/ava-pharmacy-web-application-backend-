"""
Scrape remaining product images using DDGS with retries and long delays.
"""
import time
import random
import requests
from pathlib import Path
from ddgs import DDGS

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_PRODUCTS_DIR = BASE_DIR / "media" / "products"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}

REMAINING = [
    ("dettol-antiseptic-liquid-250ml.jpg",                  "Dettol antiseptic liquid 250ml brown bottle pharmacy"),
    ("johnsons-baby-lotion-200ml.jpg",                      "Johnson's Baby Lotion 200ml pink bottle"),
    ("strepsils-honey-lemon-lozenges-24s.jpg",              "Strepsils honey lemon throat lozenges 24 pack"),
    ("sudocrem-antiseptic-healing-cream-125g.jpg",          "Sudocrem healing cream 125g white tub"),
    ("eucerin-sun-fluid-spf-50-50ml.jpg",                   "Eucerin sun protection fluid SPF50 tube"),
    ("omron-m2-upper-arm-blood-pressure-monitor.jpg",       "Omron M2 blood pressure monitor upper arm"),
    ("accu-chek-active-glucometer-starter-pack.jpg",        "Accu-Chek Active blood glucose meter kit"),
    ("pulse-oximeter-fingertip-spo2-monitor.jpg",           "fingertip pulse oximeter SpO2 heart rate monitor"),
    ("digital-thermometer-oralrectalaxillary.jpg",          "digital body thermometer clinical pharmacy"),
    ("sma-pro-follow-on-milk-900g.jpg",                     "SMA Pro follow on baby formula tin 900g"),
    ("pregnacare-plus-2828-tablets.jpg",                    "Pregnacare Plus pregnancy supplement tablets 56"),
    ("vitamin-c-1000mg-effervescent-tablets-20s.jpg",       "vitamin C 1000mg effervescent dissolving tablets tube"),
    ("ferrous-sulphate-folic-acid-200mg04mg-tablets-30s.jpg", "ferrous sulphate folic acid iron supplement tablets"),
    ("moringa-leaf-powder-200g.jpg",                        "moringa powder 200g green pouch supplement"),
    ("ibuprofen-400mg-tablets.jpg",                         "ibuprofen 400mg anti-inflammatory tablets pack"),
    ("omeprazole-20mg-capsules.jpg",                        "omeprazole 20mg gastro resistant capsules pack"),
    ("amoxicillin-500mg-capsules.jpg",                      "amoxicillin 500mg antibiotic capsules blister"),
    ("co-amoxiclav-625mg-tablets.jpg",                      "co-amoxiclav 625mg Augmentin antibiotic tablets"),
    ("metronidazole-400mg-tablets.jpg",                     "metronidazole 400mg Flagyl antibiotic tablets"),
    ("salbutamol-inhaler-100mcg.jpg",                       "salbutamol 100mcg Ventolin blue reliever inhaler"),
    ("metformin-500mg-tablets.jpg",                         "metformin 500mg diabetes tablets pack Glucophage"),
    ("glibenclamide-5mg-tablets.jpg",                       "glibenclamide 5mg diabetes tablets blister pack"),
    ("amlodipine-5mg-tablets.jpg",                          "amlodipine 5mg blood pressure tablets pack"),
    ("losartan-50mg-tablets.jpg",                           "losartan 50mg hypertension tablets blister pack"),
    ("artemetherlumefantrine-20120mg-tablets-al.jpg",       "Coartem artemether lumefantrine malaria tablets"),
]


def try_download(url, min_size=5000):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        if (r.status_code == 200
                and any(t in ct for t in ["image/", "jpeg", "png", "webp"])
                and len(r.content) > min_size):
            return r.content
    except Exception:
        pass
    return None


def search_once(query, retries=3):
    for attempt in range(retries):
        try:
            with DDGS() as d:
                results = list(d.images(query, max_results=20, size="Medium"))
                return results
        except Exception as e:
            msg = str(e)
            if "Ratelimit" in msg or "429" in msg:
                wait = 15 + attempt * 10 + random.uniform(2, 5)
                print(f"    Rate limited, waiting {wait:.0f}s...")
                time.sleep(wait)
            else:
                print(f"    DDG error: {e}")
                break
    return []


success = 0
failed = []

for filename, query in REMAINING:
    save_path = MEDIA_PRODUCTS_DIR / filename
    print(f"\n[{filename}]")

    results = search_once(query)
    downloaded = False

    skip_domains = ["wikimedia", "wikipedia", "pinterest", "instagram",
                    "facebook", "twitter", "tiktok", "reddit", "alamy",
                    "shutterstock", "gettyimages", "istockphoto"]

    for r in results:
        url = r.get("image", "")
        if not url or any(d in url.lower() for d in skip_domains):
            continue
        w, h = r.get("width", 0), r.get("height", 0)
        if w and h and (w < 150 or h < 150):
            continue
        content = try_download(url)
        if content:
            save_path.write_bytes(content)
            print(f"  ✓ {len(content):,}b from {url[:80]}")
            downloaded = True
            success += 1
            break

    if not downloaded:
        print(f"  ✗ No image found")
        failed.append(filename)

    # Be polite — avoid rate limit
    time.sleep(random.uniform(4, 7))

print(f"\n=== Done: {success}/{len(REMAINING)} ===")
if failed:
    print("Failed:")
    for f in failed:
        print(f"  {f}")
