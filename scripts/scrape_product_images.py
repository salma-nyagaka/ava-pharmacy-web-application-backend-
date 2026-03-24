"""
Scrape real product images from the web and save to media/products/.
Run from the project root: python scripts/scrape_product_images.py
"""
import os
import sys
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_PRODUCTS_DIR = BASE_DIR / "media" / "products"
MEDIA_PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# slug -> (filename in media/products/, search query)
PRODUCTS = [
    ("panadol-extra-tablets-500mg65mg",                 "panadol-extra-tablets-500mg65mg.jpg",              "Panadol Extra Tablets 500mg 65mg box"),
    ("dettol-antiseptic-liquid-250ml",                  "dettol-antiseptic-liquid-250ml.jpg",               "Dettol antiseptic liquid 250ml bottle"),
    ("johnsons-baby-lotion-200ml",                      "johnsons-baby-lotion-200ml.jpg",                   "Johnson's Baby Lotion 200ml bottle"),
    ("vicks-vaporub-50g",                               "vicks-vaporub-50g.jpg",                            "Vicks VapoRub 50g tub jar"),
    ("sensodyne-repair-protect-toothpaste-75ml",        "sensodyne-repair-protect-toothpaste-75ml.jpg",     "Sensodyne Repair Protect toothpaste 75ml tube"),
    ("strepsils-honey-lemon-lozenges-24s",              "strepsils-honey-lemon-lozenges-24s.jpg",           "Strepsils honey lemon lozenges 24 pack box"),
    ("sudocrem-antiseptic-healing-cream-125g",          "sudocrem-antiseptic-healing-cream-125g.jpg",       "Sudocrem antiseptic healing cream 125g tub"),
    ("cetaphil-gentle-skin-cleanser-250ml",             "cetaphil-gentle-skin-cleanser-250ml.jpg",          "Cetaphil gentle skin cleanser 250ml bottle"),
    ("eucerin-sun-fluid-spf-50-50ml",                   "eucerin-sun-fluid-spf-50-50ml.jpg",                "Eucerin sun fluid SPF 50 50ml tube"),
    ("omron-m2-upper-arm-blood-pressure-monitor",       "omron-m2-upper-arm-blood-pressure-monitor.jpg",    "Omron M2 upper arm blood pressure monitor"),
    ("accu-chek-active-glucometer-starter-pack",        "accu-chek-active-glucometer-starter-pack.jpg",     "Accu-Chek Active glucometer starter pack"),
    ("pulse-oximeter-fingertip-spo2-monitor",           "pulse-oximeter-fingertip-spo2-monitor.jpg",        "fingertip pulse oximeter SpO2 monitor white"),
    ("digital-thermometer-oralrectalaxillary",          "digital-thermometer-oralrectalaxillary.jpg",       "digital clinical thermometer oral body temperature"),
    ("sma-pro-follow-on-milk-900g",                     "sma-pro-follow-on-milk-900g.jpg",                  "SMA Pro Follow-On Milk formula tin 900g"),
    ("pregnacare-plus-2828-tablets",                    "pregnacare-plus-2828-tablets.jpg",                 "Pregnacare Plus tablets pack 28+28 pregnancy"),
    ("complete-multivitamins-adults-30s",               "complete-multivitamins-adults-30s.jpg",            "complete multivitamin tablets adults 30 capsules bottle"),
    ("omega-3-fish-oil-1000mg-softgels-30s",            "omega-3-fish-oil-1000mg-softgels-30s.jpg",         "omega 3 fish oil 1000mg softgels capsules 30"),
    ("vitamin-c-1000mg-effervescent-tablets-20s",       "vitamin-c-1000mg-effervescent-tablets-20s.jpg",    "vitamin C 1000mg effervescent tablets tube"),
    ("ferrous-sulphate-folic-acid-200mg04mg-tablets-30s", "ferrous-sulphate-folic-acid-200mg04mg-tablets-30s.jpg", "ferrous sulphate folic acid tablets pack pharmacy"),
    ("moringa-leaf-powder-200g",                        "moringa-leaf-powder-200g.jpg",                     "moringa leaf powder 200g bag pouch green"),
    ("ibuprofen-400mg-tablets",                         "ibuprofen-400mg-tablets.jpg",                      "ibuprofen 400mg tablets blister pack Nurofen"),
    ("aspirin-75mg-dispersible-tablets",                "aspirin-75mg-dispersible-tablets.jpg",             "aspirin 75mg dispersible tablets pack"),
    ("cetirizine-10mg-tablets-10s",                     "cetirizine-10mg-tablets-10s.jpg",                  "cetirizine 10mg antihistamine tablets pack 10"),
    ("loperamide-2mg-capsules-12s",                     "loperamide-2mg-capsules-12s.jpg",                  "loperamide 2mg capsules Imodium diarrhea 12 pack"),
    ("omeprazole-20mg-capsules",                        "omeprazole-20mg-capsules.jpg",                     "omeprazole 20mg capsules Losec blister pack"),
    ("ors-sachets-oral-rehydration-salts-10s",          "ors-sachets-oral-rehydration-salts-10s.jpg",       "ORS oral rehydration salts sachets pack 10"),
    ("amoxicillin-500mg-capsules",                      "amoxicillin-500mg-capsules.jpg",                   "amoxicillin 500mg capsules antibiotic blister pack"),
    ("co-amoxiclav-625mg-tablets",                      "co-amoxiclav-625mg-tablets.jpg",                   "co-amoxiclav 625mg tablets Augmentin pack"),
    ("ciprofloxacin-500mg-tablets",                     "ciprofloxacin-500mg-tablets.jpg",                  "ciprofloxacin 500mg tablets antibiotic blister"),
    ("metronidazole-400mg-tablets",                     "metronidazole-400mg-tablets.jpg",                  "metronidazole 400mg tablets Flagyl pack"),
    ("clotrimazole-1-cream-20g",                        "clotrimazole-1-cream-20g.jpg",                     "clotrimazole 1% cream 20g tube Canesten antifungal"),
    ("salbutamol-inhaler-100mcg",                       "salbutamol-inhaler-100mcg.jpg",                    "salbutamol inhaler 100mcg Ventolin blue inhaler"),
    ("metformin-500mg-tablets",                         "metformin-500mg-tablets.jpg",                      "metformin 500mg tablets Glucophage diabetes pack"),
    ("glibenclamide-5mg-tablets",                       "glibenclamide-5mg-tablets.jpg",                    "glibenclamide 5mg tablets diabetes blister pack"),
    ("atorvastatin-20mg-tablets",                       "atorvastatin-20mg-tablets.jpg",                    "atorvastatin 20mg tablets Lipitor cholesterol pack"),
    ("amlodipine-5mg-tablets",                          "amlodipine-5mg-tablets.jpg",                       "amlodipine 5mg tablets blood pressure blister pack"),
    ("losartan-50mg-tablets",                           "losartan-50mg-tablets.jpg",                        "losartan 50mg tablets hypertension blister pack"),
    ("artemetherlumefantrine-20120mg-tablets-al",       "artemetherlumefantrine-20120mg-tablets-al.jpg",    "artemether lumefantrine 20 120mg tablets Coartem malaria"),
    ("sulfadoxinepyrimethamine-50025mg-sp-tablets",     "sulfadoxinepyrimethamine-50025mg-sp-tablets.jpg",  "sulfadoxine pyrimethamine Fansidar tablets malaria"),
    ("tenofovirlamivudinedolutegravir-30030050mg-tld",  "tenofovirlamivudinedolutegravir-30030050mg-tld.jpg", "tenofovir lamivudine dolutegravir TLD tablets HIV antiretroviral"),
]


def download_image(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        if (r.status_code == 200
                and any(t in ct for t in ["image/", "jpeg", "png", "webp"])
                and len(r.content) > 5000):
            return r.content, ct
    except Exception:
        pass
    return None, None


def search_ddg(query, max_results=15):
    from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            return list(ddgs.images(
                query,
                max_results=max_results,
                size="Medium",
            ))
    except Exception as e:
        print(f"    DDG error: {e}")
        return []


def find_best_image(query):
    results = search_ddg(query)
    for r in results:
        url = r.get("image", "")
        if not url:
            continue
        # Skip social media and problematic sources
        skip = ["wikimedia", "wikipedia", "pinterest", "instagram", "facebook",
                "twitter", "tiktok", "reddit"]
        if any(s in url.lower() for s in skip):
            continue
        # Prefer pharmacy/health sites
        w = r.get("width", 0)
        h = r.get("height", 0)
        if w and h and (w < 150 or h < 150):
            continue
        content, ct = download_image(url)
        if content:
            return content, url
    return None, None


def main():
    results = {}
    failed = []

    for slug, filename, query in PRODUCTS:
        save_path = MEDIA_PRODUCTS_DIR / filename
        print(f"\n[{filename}]")

        content, source_url = find_best_image(query)
        if content:
            save_path.write_bytes(content)
            print(f"  ✓ {len(content):,}b from {source_url[:90]}")
            results[slug] = filename
        else:
            print(f"  ✗ Not found")
            failed.append(slug)

        time.sleep(0.8)

    print(f"\n\n=== Results: {len(results)}/{len(PRODUCTS)} downloaded ===")
    if failed:
        print(f"Failed ({len(failed)}):")
        for s in failed:
            print(f"  {s}")


if __name__ == "__main__":
    main()
