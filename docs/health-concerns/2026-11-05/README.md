# Catalog health concern review — 5 November 2026

Reviewed all 23,411 sellable items, including inactive records. Created 24 concerns, bringing the total to 44 active concerns. 13,888 products now have concern links; 9,523 have no supported match and remain untagged.

Assignments use explicit product names and the existing category/subcategory. They are browsing tags, not confirmation of clinical suitability. No medical indication was inferred solely from a brand or an unexplained medicine name. Existing manually assigned links were preserved. Previously automatic links attributable to the legacy curation note were replaced where no longer supported: 6,641 new links, 3,364 removed automatic links, 18,183 final links.

The command defaults to a dry run and can be rerun without duplicate concerns, links or notes. New concerns are created only when products match. No schema change is needed: the existing Variant–HealthConcern relationship is used.

The storefront navigation now follows pagination instead of showing just the first 20 concerns. The public API exposes all 44. Product filtering was verified for diabetes monitoring (56 visible items), period care (198), and sun protection (533). Inactive items remain excluded from the storefront.

Validation: four focused tests passed; frontend TypeScript/production build passed. Full before/after fingerprints confirm product details, variant fields except curation notes, all 64,094 stock records and all 64,094 store listings remained unchanged.

Backup: `/private/tmp/ava-health-concerns-20261105T182256Z/database.dump`.

Detailed assignments and removed automatic links are in assignments.json. Counts are in summary.json; fingerprints are in verification.json.

| Concern | Linked items (all records) |
| --- | ---: |
| Acne & Blemishes | 135 |
| Allergy Relief | 36 |
| Anti-ageing Skin Care | 58 |
| Baby & Child Care | 1,224 |
| Bone, Joint & Muscle | 1,063 |
| Cold, Cough & Flu | 312 |
| Constipation Care | 4 |
| Dandruff Care | 21 |
| Diabetes & Blood Glucose | 57 |
| Diarrhoea & Rehydration | 6 |
| Digestive Health | 99 |
| Dry Skin & Hydration | 852 |
| Ear Care | 71 |
| Eczema & Dermatitis Care | 31 |
| Energy & Sports Performance | 673 |
| Eye Care | 251 |
| Fertility & Ovulation | 65 |
| First Aid | 1,050 |
| Foot Care | 247 |
| Hair & Scalp | 1,018 |
| Hair Thinning & Hair Loss | 7 |
| Heart & Circulation | 144 |
| Heartburn & Acid Reflux | 29 |
| Immune Support | 69 |
| Incontinence Care | 129 |
| Memory & Focus | 7 |
| Men's Health | 3 |
| Menopause Care | 6 |
| Nasal & Sinus Care | 158 |
| Oral Care | 841 |
| Pain & Fever | 91 |
| Period Care | 201 |
| Pregnancy & Breastfeeding | 163 |
| Respiratory Health | 121 |
| Scars & Stretch Marks | 19 |
| Sensitive Skin | 52 |
| Sexual Health | 220 |
| Skin Health | 4,414 |
| Sleep & Stress | 148 |
| Smoking Cessation | 31 |
| Sun Protection | 535 |
| Vitamins & Nutrition | 3,126 |
| Weight Management | 17 |
| Women's Health | 379 |
