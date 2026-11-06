# Brand directory and logo sourcing — 6 November 2026

The Top Brands menu supports All, # and A–Z filtering, 24 brands per page, Previous/Next and direct page selection. The Brands page uses the same directory with search and 48 brands per page. All 1,471 active brands remain reachable. Brand links filter products by the existing brand slug.

Scraped researched official brand/manufacturer pages. 57 logo candidates were found. Manual review excluded 8 unrelated corporate/sub-brand/promotional or white-on-white images. The importer applied 36 new exact-name logos, preserved 11 existing logos, rejected 1 SVG with active/external content, and skipped 1 unmatched name. No existing logos were replaced.

This does not claim logo coverage for every brand. Missing logos remain initials and are listed in missing-logos.csv. Source URLs and imported content hashes are in logos.json. Original logo paths are backed up in logos-before.json. Product/brand assignments and stock were not changed.

Validation: frontend TypeScript/production build passed; two image validation tests passed; browser verified Z filtering (36 matches) and Top Brands Next (25–48 of 1,471). Imported files exist in media storage.

Repeat sourcing with scripts/scrape_researched_brand_logos.py, review its candidate manifest, then run manage.py import_brand_logos with --manifest and --report-dir. It defaults to a dry run; --apply imports missing logos only.
