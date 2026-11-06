# Admin menu fixes — 5 November 2026

## Data findings

Read-only inspection of the local database found 29 categories, 0 subcategories, 20 health concerns, 157 brands, 22,192 products and 23,411 variants. The old 20-row default API pagination truncated the reference management lists; 20 health concerns is the actual count. Imported categories are flat. The QA subcategory was removed during the user-approved test cleanup; this change does not fabricate a new hierarchy or reclassify imported medicines.

Inventory's 2,342 figure is the number of pages at 10 variants per page, not the number of variants. The table footer reports its filtered matching count. KPI cards now explicitly describe the entire catalog, including when the table is filtered. Observed whole-catalog counts: 8,344 in stock, 3,201 low/backorder, 11,866 out/inactive; these sum to 23,411 variants.

## Changes

- Admin category, subcategory, brand, health-concern and promotion reference lists include every record, including inactive records. Category/brand/health-concern active and inactive counts live in the toolbar. Removed the brand logo KPI.
- Products uses server pagination, filtering and sorting, a compact list serializer, full detail on edit, database-wide KPI totals and bounded pagination controls. The frontend no longer downloads all merchandise before rendering. Brand product counts use full-database annotations.
- Deals no longer traverses the whole product catalog. Product promotion targets support debounced server search. With the QA promotions removed, its empty state is expected.
- Inventory uses whole-catalog status totals and labels. Both merchandise pages debounce search and discard stale responses. POS options load only for the selected New Stock product, and sorting keeps page boundaries stable. Pagination metadata uses the actual server-capped page size.
- Role-specific user counts, headings and actions exclude unrelated roles. Doctors, pediatricians, prescriptions and user lists follow all API pages. Shared header, KPI, toolbar and table styles align the clinical administration pages.
- Dashboard and Reports share `/admin/dashboard`, with Overview and Reports & analytics tabs. `/admin/reports` redirects to `/admin/dashboard?view=reports` and the duplicate sidebar entry is removed.
- Compliance uses scoped tabs, cards and form grids; Settings uses aligned responsive cards, consistent controls and a correctly sized checkbox.
- Ordinary unreviewed variant creation no longer mistakes serializer defaults for an explicitly submitted clinical decision. Explicit clinical/regulatory changes still require a credentialed reviewer. A legacy medication-field test now supplies the existing synthetic credential fixture.

## Cache behavior and operations

Admin product and inventory list responses use Django's shared cache for 60 seconds, keyed by generation, request URL and authenticated user. The generation is scoped to the database. Product-app saves, deletes and variant health-concern changes invalidate the generation **after successful transaction commit**, including stock saves from checkout and POS sync. A new product, stock change or variant deletion is visible to the next request; the application does not wait for a Celery worker to invalidate reads. Old generation entries expire normally.

By default the cache uses `tmp/admin-read-cache` so local web and Celery processes share invalidations. Set `ADMIN_CACHE_URL` to a dedicated Redis database for multiple hosts. `ADMIN_CATALOG_CACHE_TTL` controls the response TTL. Celery Beat schedules `apps.products.tasks.warm_admin_catalog_summary` once per minute; warming requires the configured broker, worker and Beat. No new broker service was installed or started for this change. Reads and invalidation work without Celery.

Bulk ORM updates and raw SQL bypass Django save/delete signals. Any future bulk catalog writer must call `apps.products.admin_cache.invalidate_admin_catalog()` in its transaction. Existing catalog/stock API writes use model saves/deletes. External direct database changes also expire out of the response cache after the TTL.

## Verification

- Final TypeScript/Vite production build passed.
- Django system check passed.
- 96 tests passed across admin reads, catalog CRUD, store inventory integrity, inventory sync and compliance controls in an isolated test database. No acceptance fixtures were added to the local development database.
- Browser checks opened every visible main admin menu and both dashboard tabs. Verified category/brand/concern toolbar counts, role-specific counts, Deals empty state, whole-inventory totals and pagination. No browser console errors appeared in that run; the reported product-page 404 was not reproduced after the loading changes.
- Local API timings (cold then warm, excluding browser rendering): Products page of 6: 0.310s / 0.002s; Inventory page of 10: 1.091s / 0.002s. These are single local measurements, not production performance guarantees.

Existing unrelated workspace edits were retained. This is a local implementation/build verification, not a production deployment or completion of all manual acceptance cases.

## Follow-up: database-wide KPI counts

All reference/role/service KPI cards now use `/admin/record-stats/?section=...` SQL aggregates. This endpoint ignores table search, status and pagination parameters. The only supported restriction is the explicit user-role or clinician-type menu scope. It covers categories/subcategories, brands, health concerns, customers/staff, clinicians, prescriptions, deals, orders, invoices, support, lab requests, lab-test categories and payout counts/amounts. Product and inventory cards retain their existing whole-database summary endpoint.

Invoices now shows total, paid and unpaid invoice counts instead of page-local row counts and a page number. Unpaid excludes refunded invoices; drafts are orders, not invoices. The frontend refreshes these direct database counts after its underlying records change, on focus and every 30 seconds. Failed requests display an unavailable indicator rather than substituting a page count. Paged-table result counts and pagination footers continue to describe the table's matching records.

Verified a browser search with no matches and an inactive-brand filter: the table showed zero results while the database KPIs remained 157 total / 157 active / 0 inactive. The production frontend build passed. New regression cases cover more than 20 records, ignored table filters, role boundaries, invoices, clinician types, support and date-based deal statuses.
