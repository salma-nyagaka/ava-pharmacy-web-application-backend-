"""
Fetch remaining product images using direct URLs from known pharmacy/retailer sites.
"""
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_PRODUCTS_DIR = BASE_DIR / "media" / "products"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

# filename -> list of direct image URLs to try in order
REMAINING = {
    "dettol-antiseptic-liquid-250ml.jpg": [
        "https://m.media-amazon.com/images/I/61kQSCjT7DL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/71XA7kP3nGL._AC_SL1500_.jpg",
        "https://images.ctfassets.net/hhv516v5f7sj/dettol-antiseptic-liquid-250ml.jpg",
    ],
    "johnsons-baby-lotion-200ml.jpg": [
        "https://m.media-amazon.com/images/I/61NLbzVfS6L._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/71nxiZ0KYVL._AC_SL1500_.jpg",
        "https://www.boots.com/medias/sys_master/images/hac/h44/10163454345246.jpg",
    ],
    "strepsils-honey-lemon-lozenges-24s.jpg": [
        "https://m.media-amazon.com/images/I/71T8yKNRwpL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/81k8J0GKULL._AC_SL1500_.jpg",
        "https://images-its.chemistdirect.co.uk/Strepsils-Honey-Lemon-Throat-Lozenges-24-Pack-1.jpg",
    ],
    "sudocrem-antiseptic-healing-cream-125g.jpg": [
        "https://m.media-amazon.com/images/I/61nM-lRzd7L._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/71S0iWdcbaL._AC_SL1500_.jpg",
        "https://images-its.chemistdirect.co.uk/Sudocrem-Antiseptic-Healing-Cream-125g-1.jpg",
    ],
    "eucerin-sun-fluid-spf-50-50ml.jpg": [
        "https://m.media-amazon.com/images/I/61RgzgFCdVL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/71B8qk0w5pL._AC_SL1500_.jpg",
        "https://www.eucerin.co.uk/-/media/project/loreal/brand-sites/eucerin/emea/uk/products/sun-fluids/sun-fluid-non-tinted.jpg",
    ],
    "omron-m2-upper-arm-blood-pressure-monitor.jpg": [
        "https://m.media-amazon.com/images/I/61IcMBpzaJL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/71QKBT0bmNL._AC_SL1500_.jpg",
        "https://omronhealthcare-eu.com/media/catalog/product/o/m/omron-m2.jpg",
    ],
    "accu-chek-active-glucometer-starter-pack.jpg": [
        "https://m.media-amazon.com/images/I/71ixkbFPlhL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/810rlOe5mEL._AC_SL1500_.jpg",
        "https://www.accu-chek.com/content/dam/accu-chek/images/products/meters/active/accu-chek-active-meter-set.jpg",
    ],
    "pulse-oximeter-fingertip-spo2-monitor.jpg": [
        "https://m.media-amazon.com/images/I/61k4BilY4cL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/71cLwF+aKgL._AC_SL1500_.jpg",
        "https://images-its.chemistdirect.co.uk/Pulse-Oximeter-Fingertip-SpO2-Monitor.jpg",
    ],
    "digital-thermometer-oralrectalaxillary.jpg": [
        "https://m.media-amazon.com/images/I/61yQ9yM1xEL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/71e98oRbV2L._AC_SL1500_.jpg",
        "https://images-its.chemistdirect.co.uk/Digital-Thermometer.jpg",
    ],
    "sma-pro-follow-on-milk-900g.jpg": [
        "https://m.media-amazon.com/images/I/71jZQVPzCBL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/81qZnxNEhxL._AC_SL1500_.jpg",
        "https://www.boots.com/medias/sys_master/images/h23/h6d/10163571433502.jpg",
    ],
    "pregnacare-plus-2828-tablets.jpg": [
        "https://m.media-amazon.com/images/I/71bMTnTIPvL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/71Xf4HJ7GIL._AC_SL1500_.jpg",
        "https://images-its.chemistdirect.co.uk/Pregnacare-Plus-Omega-3-56-Tablets.jpg",
    ],
    "vitamin-c-1000mg-effervescent-tablets-20s.jpg": [
        "https://m.media-amazon.com/images/I/71Mc55DqL+L._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/61cLaEuS8vL._AC_SL1500_.jpg",
        "https://images-its.chemistdirect.co.uk/Vitamin-C-1000mg-Effervescent-Tablets-20.jpg",
    ],
    "ferrous-sulphate-folic-acid-200mg04mg-tablets-30s.jpg": [
        "https://m.media-amazon.com/images/I/61O1bAFzpXL._AC_SX679_.jpg",
        "https://wayspharmacy.co.uk/cdn/shop/files/ferrous-sulphate-folic-acid.jpg",
        "https://images-its.chemistdirect.co.uk/Ferrous-Sulphate-Folic-Acid-Tablets.jpg",
    ],
    "moringa-leaf-powder-200g.jpg": [
        "https://m.media-amazon.com/images/I/71OT2J7WVNL._AC_SX679_.jpg",
        "https://m.media-amazon.com/images/I/81Q5kV2THKL._AC_SL1500_.jpg",
    ],
    "ibuprofen-400mg-tablets.jpg": [
        "https://m.media-amazon.com/images/I/71kd9NWdWqL._AC_SX679_.jpg",
        "https://images-its.chemistdirect.co.uk/Ibuprofen-400mg-Tablets-24s.jpg",
        "https://www.boots.com/medias/sys_master/images/h89/h2c/10163475005470.jpg",
    ],
    "omeprazole-20mg-capsules.jpg": [
        "https://m.media-amazon.com/images/I/71FzZp9UKCL._AC_SX679_.jpg",
        "https://images-its.chemistdirect.co.uk/Omeprazole-20mg-Gastro-Resistant-Capsules.jpg",
        "https://www.boots.com/medias/sys_master/images/h1c/hcd/10163448954910.jpg",
    ],
    "amoxicillin-500mg-capsules.jpg": [
        "https://wayspharmacy.co.uk/cdn/shop/files/amoxicillin-500mg-capsules.jpg",
        "https://m.media-amazon.com/images/I/61u2Vh4AKZL._AC_SX679_.jpg",
        "https://www.albionbd.com/wp-content/uploads/2021/08/Amoxicillin-500-Capsule.jpg",
    ],
    "co-amoxiclav-625mg-tablets.jpg": [
        "https://m.media-amazon.com/images/I/71eTUE+x8sL._AC_SX679_.jpg",
        "https://www.albionbd.com/wp-content/uploads/2021/08/Co-Amoxiclav-625-Tablet.jpg",
        "https://5.imimg.com/data5/SELLER/Default/2021/co-amoxiclav-625mg-tablets.jpg",
    ],
    "metronidazole-400mg-tablets.jpg": [
        "https://m.media-amazon.com/images/I/71zYlCbVhML._AC_SX679_.jpg",
        "https://www.albionbd.com/wp-content/uploads/2021/08/Metronidazole-400-Tablet.jpg",
        "https://images-its.chemistdirect.co.uk/Metronidazole-400mg-Tablets.jpg",
    ],
    "salbutamol-inhaler-100mcg.jpg": [
        "https://m.media-amazon.com/images/I/61aR1HZ9W6L._AC_SX679_.jpg",
        "https://images-its.chemistdirect.co.uk/Salamol-100mcg-CFC-Free-Inhaler.jpg",
        "https://wayspharmacy.co.uk/cdn/shop/files/salbutamol-inhaler.jpg",
    ],
    "metformin-500mg-tablets.jpg": [
        "https://m.media-amazon.com/images/I/71NXyKFPf1L._AC_SX679_.jpg",
        "https://www.albionbd.com/wp-content/uploads/2021/08/Metformin-500-Tablet.jpg",
        "https://5.imimg.com/data5/SELLER/Default/2021/metformin-500mg-tablets.jpg",
    ],
    "glibenclamide-5mg-tablets.jpg": [
        "https://5.imimg.com/data5/SELLER/Default/2021/5/glibenclamide-5mg-tablets.jpg",
        "https://www.albionbd.com/wp-content/uploads/2021/08/Glibenclamide-5-Tablet.jpg",
        "https://m.media-amazon.com/images/I/61KdJzXb2FL._AC_SX679_.jpg",
    ],
    "amlodipine-5mg-tablets.jpg": [
        "https://m.media-amazon.com/images/I/61ZbxZDzqRL._AC_SX679_.jpg",
        "https://www.albionbd.com/wp-content/uploads/2021/08/Amlodipine-5-Tablet.jpg",
        "https://5.imimg.com/data5/SELLER/Default/2021/amlodipine-5mg-tablets.jpg",
    ],
    "losartan-50mg-tablets.jpg": [
        "https://m.media-amazon.com/images/I/71XpZIcHE7L._AC_SX679_.jpg",
        "https://www.albionbd.com/wp-content/uploads/2021/08/Losartan-50-Tablet.jpg",
        "https://5.imimg.com/data5/SELLER/Default/2021/losartan-50mg-tablets.jpg",
    ],
    "artemetherlumefantrine-20120mg-tablets-al.jpg": [
        "https://m.media-amazon.com/images/I/61Gm3tIBKLL._AC_SX679_.jpg",
        "https://gdmedz.net/wp-content/uploads/artemether-lumefantrine-coartem.jpg",
        "https://5.imimg.com/data5/SELLER/Default/2021/artemether-lumefantrine-tablets.jpg",
    ],
}

session = requests.Session()
session.headers.update(HEADERS)

success = 0
failed = []

for filename, urls in REMAINING.items():
    save_path = MEDIA_PRODUCTS_DIR / filename
    print(f"\n[{filename}]")
    downloaded = False

    for url in urls:
        try:
            r = session.get(url, timeout=12, allow_redirects=True)
            ct = r.headers.get("Content-Type", "")
            if (r.status_code == 200
                    and any(t in ct for t in ["image/", "jpeg", "png", "webp"])
                    and len(r.content) > 5000):
                save_path.write_bytes(r.content)
                print(f"  ✓ {len(r.content):,}b from {url[:80]}")
                downloaded = True
                success += 1
                break
            else:
                print(f"  - Skip {url[:60]} (HTTP {r.status_code}, {len(r.content)}b, {ct[:30]})")
        except Exception as e:
            print(f"  - Error {url[:60]}: {e}")
        time.sleep(0.3)

    if not downloaded:
        failed.append(filename)

    time.sleep(0.5)

print(f"\n=== Done: {success}/{len(REMAINING)} ===")
if failed:
    print(f"Still failed ({len(failed)}):")
    for f in failed:
        print(f"  {f}")
