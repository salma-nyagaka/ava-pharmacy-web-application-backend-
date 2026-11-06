# Deal and coupon checklist results — 6 November 2026

- [x] S05-06: Missing start/end dates and end-before-start rejected. Partial edits validate against the other saved date. Deal modal shows field-specific date errors.
- [x] S05-07: Coupon and promotion serializers reject nonpositive discounts and percentages above 100. Code uniqueness checks ignore case and surrounding whitespace; accepted codes normalize to uppercase. Existing code is allowed when editing its own record. Invalid legacy values cannot activate coupons/offers. Modal validates percentage limits before saving.
- [x] S05-08: Coupon availability checks active state, time window and usage limits. Minimum spend checks eligible item subtotal; prescription/controlled items neither receive coupon discounts nor qualify toward its minimum. All-excluded carts are rejected. Checkout recalculates discounts, including minimum-spend rules. Product-targeted offers do not discount other items.
- [x] S05-09: Expired, future and draft/inactive promotions are excluded from public offer queries and do not discount products. Inclusive start/end dates admit an active offer on its saved dates.

Validation: 12 backend tests passed (offer_acceptance, homepage_offers, existing coupon expiry/minimum/replacement/removal acceptance test). Frontend TypeScript build passed. Tests used isolated test records, not the live catalog. An old order fixture was corrected to respect the one-SKU-per-product constraint.

Scope: current item exclusion is prescription/controlled classification. Coupons do not currently offer an arbitrary exclusion-list editor. Deals (automatic promotions) and checkout coupon records remain separate systems; this work does not convert deal codes into checkout coupons.
