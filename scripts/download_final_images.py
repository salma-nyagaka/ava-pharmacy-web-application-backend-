"""
Download the remaining product images using verified direct URLs.
"""
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEST = BASE_DIR / "media" / "products"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

# filename -> list of verified URLs to try
IMAGES = [
    ("dettol-antiseptic-liquid-250ml.jpg", [
        "https://www.expresschemist.co.uk/pics/products/47328/2/dettol-liquid-antiseptic-disinfectant-250ml.jpg",
        "https://shop.rowlandspharmacy.co.uk/cdn/shop/files/Dettol_Liquid_Antiseptic_250ml_50158072_T1_b76030aa-4303-4719-a76c-114479014c7b.jpg?v=1772210181",
        "https://m2.ukmeds.co.uk/media/catalog/product/cache/74c1057f7991b4edb2bc7bdaa94de933/d/e/dettol-liquid-antiseptic-disinfectant-250ml--1571516983_1_1.png",
    ]),
    ("johnsons-baby-lotion-200ml.jpg", [
        "https://britishchemist.co.uk/wp-content/uploads/2022/12/JOH0484N.jpg",
        "https://www.peakpharmacy.co.uk/uploads/images/products/large/peakpharmacy-johnsons-baby-lotion-200ml.jpg",
    ]),
    ("strepsils-honey-lemon-lozenges-24s.jpg", [
        "https://www.expresschemist.co.uk/pics/products/48028/2/strepsils-honey-and-lemon.jpg",
        "https://wayspharmacy.co.uk/cdn/shop/files/WeChat__20260108112521.jpg?v=1767871592",
    ]),
    ("sudocrem-antiseptic-healing-cream-125g.jpg", [
        "https://www.expresschemist.co.uk/pics/products/2574/2/Sudocrem_Antiseptic_Healing_Cream_125g_tub.jpg",
    ]),
    ("eucerin-sun-fluid-spf-50-50ml.jpg", [
        "https://www.expresschemist.co.uk/pics/products/51147/0/eucerin-sun-protection-sun-fluid-mattifying-face-spf50-50ml.jpg",
    ]),
    ("omron-m2-upper-arm-blood-pressure-monitor.jpg", [
        "https://www.peakpharmacy.co.uk/uploads/images/products/large/peakpharmacy-omron-m2-basic-blood-pressure-monitor-1722422013Omron-M2-Basic-Blood-Pressure-Monitor.jpg",
    ]),
    ("pregnacare-plus-2828-tablets.jpg", [
        "https://www.expresschemist.co.uk/pics/products/47465/2/vitabiotics-pregnacare-plus-omega3-capsules-56.jpg",
        "https://pharmacykwik.co.uk/cdn/shop/products/word_image444873.png?v=1571438607",
    ]),
    ("vitamin-c-1000mg-effervescent-tablets-20s.jpg", [
        "https://www.expresschemist.co.uk/pics/products/46895/2/haliborange-vitamin-c-1000mg-effervescent-tablets-orange-(20).jpg",
    ]),
    ("ferrous-sulphate-folic-acid-200mg04mg-tablets-30s.jpg", [
        "https://www.simplymedsonline.co.uk/images/detailed/30/ferrous_sulfate_200mg_tablets.jpg",
        "https://livewellnationwide.co.uk/wp-content/uploads/ferrous-sulphate-200mg-tablets.jpg",
    ]),
    ("moringa-leaf-powder-200g.jpg", [
        "https://www.terrasoul.com/cdn/shop/products/moringa-leaf-powder-front.jpg",
        "https://m.media-amazon.com/images/I/71OT2J7WVNL._AC_SL1500_.jpg",
    ]),
    ("omeprazole-20mg-capsules.jpg", [
        "https://www.expresschemist.co.uk/pics/products/58629/2/numark-heartburn-and-acid-reflux-gastro-resistant-20mg-7-tablets.jpg",
        "https://www.clearchemist.co.uk/media/catalog/product/cache/02b790335c04022f348f83b7ab327ad9/o/m/omeprazole.jpg",
    ]),
    ("amoxicillin-500mg-capsules.jpg", [
        "https://www.expresschemist.co.uk/pics/products/amoxicillin-500mg-capsules.jpg",
        "https://www.clearchemist.co.uk/media/catalog/product/cache/02b790335c04022f348f83b7ab327ad9/a/m/amoxicillin500mg.jpg",
    ]),
    ("co-amoxiclav-625mg-tablets.jpg", [
        "https://www.expresschemist.co.uk/pics/products/co-amoxiclav-625mg.jpg",
    ]),
    ("salbutamol-inhaler-100mcg.jpg", [
        "https://static.hightownpharmacy.co.uk/products/salbutamol-inhaler-100mcg.webp",
    ]),
    ("metformin-500mg-tablets.jpg", [
        "https://www.clearchemist.co.uk/media/catalog/product/cache/02b790335c04022f348f83b7ab327ad9/m/e/met84.jpg",
    ]),
    ("glibenclamide-5mg-tablets.jpg", [
        "https://www.clearchemist.co.uk/media/catalog/product/cache/02b790335c04022f348f83b7ab327ad9/g/l/glibenclamide.jpg",
        "https://www.expresschemist.co.uk/pics/products/glibenclamide-5mg.jpg",
    ]),
    ("amlodipine-5mg-tablets.jpg", [
        "https://www.clearchemist.co.uk/media/catalog/product/cache/02b790335c04022f348f83b7ab327ad9/p/o/pom_awaiting_image_1246.jpg",
    ]),
    ("losartan-50mg-tablets.jpg", [
        "https://www.clearchemist.co.uk/media/catalog/product/cache/02b790335c04022f348f83b7ab327ad9/l/o/losartan.jpg",
        "https://www.expresschemist.co.uk/pics/products/losartan-50mg.jpg",
    ]),
    ("artemetherlumefantrine-20120mg-tablets-al.jpg", [
        "https://gdmedz.net/wp-content/uploads/2021/09/Coartem-artemether-lumefantrine.jpg",
        "https://www.medicinepath.net/wp-content/uploads/artemether-lumefantrine-tablets.jpg",
    ]),
]

success = 0
failed = []

session = requests.Session()
session.headers.update(HEADERS)

for filename, urls in IMAGES:
    save_path = DEST / filename
    print(f"\n[{filename}]")
    downloaded = False

    for url in urls:
        try:
            r = session.get(url, timeout=12, allow_redirects=True)
            ct = r.headers.get("Content-Type", "")
            size = len(r.content)
            if (r.status_code == 200
                    and any(t in ct for t in ["image/", "jpeg", "png", "webp"])
                    and size > 3000):
                save_path.write_bytes(r.content)
                print(f"  ✓ {size:,}b from {url[:85]}")
                downloaded = True
                success += 1
                break
            else:
                print(f"  - {url[:75]} → HTTP {r.status_code} {ct[:25]} {size}b")
        except Exception as e:
            print(f"  - {url[:75]} → {e}")
        time.sleep(0.3)

    if not downloaded:
        failed.append(filename)

print(f"\n=== {success}/{len(IMAGES)} downloaded ===")
if failed:
    print("Failed:")
    for f in failed:
        print(f"  {f}")
