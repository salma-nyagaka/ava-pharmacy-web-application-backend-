# Product enrichment - 1 November 2026

Scope: existing source links only. 22 linked variants checked; 10 enriched, 12 unchanged. This is not a scrape of all 22,733 active non-synthetic catalog variants. Most catalog variants have no saved source link.

Descriptions are short factual rewrites, with specifications checked against product/range/pack details. Generic social logos, retailer shipping copy and unverified medical directions/claims were excluded. Existing verified images and non-placeholder content were preserved; three images were refreshed from structured product image URLs. All ten current images were visually reviewed. Prices, stock, prescription status and regulatory data were not changed.

## Applied changes

| Variant | Product | Changed fields | Source |
|---|---|---|
| 1451 | AUNT JACKIE'S CURLS & COILS DON'T SHRINK FLAXSEED ELONGATING CURLING GEL 426G | description, pack_size, curation_notes; image visually verified | [Source](https://ultrapanama.com/product/aunt-jackies-dont-shrink-flaxseed-elongating-curling-gel-426g/) |
| 2928 | BETADINE SURGICAL SCRUB 500Ml | description, short_description, pack_size, curation_notes; image visually verified | [Source](https://www.truemeds.in/medicine/betadine-75-scrub-500-ml-tm-scub1-000003) |
| 22911 | WELLA SHOCKWAVES HAIR MOUSSE VOLUME 5 200ML | description, short_description, pack_size, curation_notes, image, image_source_url, image_checked_at; image visually verified | [Source](https://head2toes.ae/product/wella-shockwaves-volume-mousse-200ml/) |
| 23004 | WISDOM ACTIVE WHITENING CHARCOAL TOOTHBRUSH MEDIUM | description, short_description, curation_notes, image, image_source_url, image_checked_at; image visually verified | [Source](https://www.hampdensupply.com/42462-hs-wisdom-active-whitening-charcoal-toothbrush) |
| 23013 | WISDOM CLEAN BETWEEN EASY NSLIDE FLOSSERS 30*S | description, short_description, pack_size, curation_notes; image visually verified | [Source](https://shop.pharmaplus.co.ke/products/wisdom-clean-between-easyslide-y-shaped-flossers-30-s) |
| 23025 | WISDOM FRESH BREATH SPRAY 12.5ML | description, short_description, pack_size, curation_notes, image, image_source_url, image_checked_at; image visually verified | [Source](https://www.weldricks.co.uk/products/wisdom-fresh-breath-spray-125ml) |
| 23028 | WISDOM FRESH EFFECT FRESHMINT MOUTHWASH 500ML | pack_size, curation_notes; image visually verified | [Source](https://henryandhunter.co.uk/product/wisdom-fresh-effect-freshmint-mouthwash-500ml/) |
| 23085 | WISDOM TONGUE CLEANER FRESH EFFECT | description, short_description, curation_notes; image visually verified | [Source](https://britishchemist.co.uk/product/wisdom-fresh-effect-tongue-cleaner/) |
| 23090 | WISDOM TRAVEL TOOTHBRUSH MEDIUM | description, short_description, curation_notes; image visually verified | [Source](https://wisdom-toothbrushes.com/shop/manual-toothbrushes/travel-toothbrush/) |
| 23092 | WISDOM XTRA CLEAN TWIN PACK MEDIUM TOOTHBRUSH | pack_size, curation_notes; image visually verified | [Source](https://www.dmrckenya.co.ke/product/wisdom-toothbrush-xtra-clean-twin-pack-medium/) |

## Unchanged source pages

| Variant | Result | Reason |
|---|---|---|
| 22865 | failed | 429 Client Error: Too Many Requests for url: https://halohealthcare.com/products/webber-naturals-coenzyme-q10-200mg-60-softgels |
| 22914 | failed | 429 Client Error: Too Many Requests for url: https://shopxonline.lk/products/wella-silvikrin-natural-hold-hair-spray-250ml |
| 22915 | failed | 429 Client Error: Too Many Requests for url: https://www.tjbeautyproducts.co.uk/products/wella-professionals-silvikrin-classic-natural-hold-hairspray-250ml |
| 22922 | failed | 403 Client Error: Forbidden for url: https://groceries.morrisons.com/products/wella-shockwaves-ultra-strong-power-hold-hairspray-250ml/100684139 |
| 22959 | failed | 429 Client Error: Too Many Requests for url: https://friser.pl/Wet-Brush/mini-squirt-szczotka-do-wlosow-purple-fioletowa |
| 23003 | no_product_metadata | No usable structured product metadata; no bypass attempted |
| 23024 | failed | 429 Client Error: Too Many Requests for url: https://jdssupercare.com/products/wisdom-enamel-protect-toothbrush |
| 23026 | failed | HTTPSConnectionPool(host='garnetpharmacy.co.ke', port=443): Read timed out. (read timeout=8) |
| 23077 | failed | 429 Client Error: Too Many Requests for url: https://www.poundland.co.uk/products/wisdom-smokers-fluoride-toothpaste-extra-fresh-mint-50ml |
| 23081 | skipped | robots.txt disallows this path |
| 23082 | skipped | robots.txt disallows this path |
| 23084 | skipped | robots.txt disallows this path |

## Verification and retained records

- Ten public API product-detail responses and exact variant descriptions/images verified.
- Price and inventory snapshots match before and after every update.
- No synthetic QA catalog products processed. No product/variant identifiers, barcodes or medical strengths inferred.
- Source failures were retained; no access-control or robots restrictions bypassed.
- [Scraped source metadata](enrichment-sources.json)
- [Reviewed content and image plan](enrichment-plan.json)
- [Before/after journal](enrichment-journal.json) retains original values; original image files were not deleted.
- [Public API and stock verification](verification.json)
- [Image review contact sheet](enriched-images-review.jpg)

For the remaining catalog, provide source URLs or authorize additional source discovery. Existing-link-only scope cannot enrich rows without a linked page.
