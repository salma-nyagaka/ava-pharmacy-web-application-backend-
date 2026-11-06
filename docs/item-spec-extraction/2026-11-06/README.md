# Explicit strength and pack-size extraction — 6 November 2026

Reviewed 23,411 imported sellable items (`LEGACY-V-` SKUs). Filled 4,109 missing strengths and 15,473 missing pack sizes across 17,195 items. Existing nonblank values were preserved. Only Variant.strength and Variant.pack_size were changed; complete before/after fingerprints for all other product, item, inventory and store-listing fields are in verification.json, along with the database backup location.

Values come only from the current imported product names. No clinical dose, ingredient strength, strength/ingredient correspondence or pack count was researched or inferred. An explicit `100’S` becomes `100 units`, without assuming the dispensing unit. A printed concentration such as `250MG/5ML` is treated as one strength and its denominator is not reused as pack size. A separate printed `100ML` becomes the pack size. Multiple distinct measurements, alternative strengths, multipacks and equipment capacities remain for review. Marketing/composition percentages are not treated as strengths.

Zulu MR remains blank in both fields because its source name does not state either measurement. PENAMOX 250MG/5ML suspension 100ML now has strength `250 mg/5 mL` and pack size `100 mL`.

assignments.json preserves old and resulting values for every item. review.csv contains 21,024 items with missing or uncertain measurements; many non-medicine items do not state a strength, and blank fields need not imply a data error. ambiguous-measurements.csv is the smaller queue of actual ambiguity/conflict/capacity cases (915 items), excluding cases that merely lack printed values.

The extraction command defaults to a preview. Re-running it preserves previously filled values. The legacy importer was adjusted to preserve existing strengths on later re-imports.
