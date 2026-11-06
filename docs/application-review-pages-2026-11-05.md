# Application review ownership

Current status: the standalone Compliance workspace and restricted account evidence page have been removed from the frontend. The implementation notes below describe the earlier relocation and are superseded where they refer to those pages.

Application review stays in each existing operational page:

- `/admin/users?role=pharmacist`: account management plus an expandable application/licence review panel. The panel supports licence details, protected evidence download, independent evidence verification, credential verification and suspension. `/admin/users?role=pharmacist&review=credentials` opens the panel directly.
- `/admin/doctors?type=Doctor`: existing doctor application review.
- `/admin/doctors?type=Pediatrician`: existing pediatrician application review.
- `/admin/prescriptions`: prescriber/authenticity/original-receipt evidence is now inside the selected prescription's details, next to the review decision controls.
- `/admin/lab-partners`: existing Applications tab and approval queue.

The pharmacist dashboard's prescription detail also uses the shared verification panel so pharmacists retain the same verification capability in their operational workflow.

Admin Compliance no longer has duplicate credential and prescription review tabs. It links to the five operational pages. Pharmacy-wide catalogue safety, medicine assessments, privacy, general evidence, operational reviews and readiness remain there. Professional credential evidence may be visible for audit, but its verification action directs administrators to the Pharmacists page. Pharmacists retain their own credential-status section in their non-admin compliance workspace.

No backend permissions, verification requirements, professional eligibility checks or data records were changed. The implementation only relocates UI controls using existing protected endpoints. No applications were approved and no evidence was verified during implementation.

Validation: TypeScript/Vite production build and diff checks passed. Browser checks confirmed that admin Compliance has the review links and no duplicate credential/prescription tabs, and that the Pharmacists link opens the licence-review panel on the correct page. The local dataset has no pharmacist applications or prescription records, so actual approval submissions were not exercised in the live database.

## Product recalls

Recall creation, affected-order dispositions and closure now live at `/admin/products-stock?view=recalls`. Compliance provides a link instead of a duplicate recall tab. A selected Products & Stock item prefills its exact SKU detail ID. Pharmacists and inspectors retain protected access through `/product-recalls`; inspectors remain read-only. Existing backend credential checks and recall holds are unchanged.

The current local admin account receives HTTP 403 because it has no current verified pharmacist credential with clinical-review permission. The relocated page explains this requirement and links to credential review rather than displaying an unusable form. No credentials were granted and no recall was opened during verification. Frontend build passed and browser navigation confirmed the new tab and access message.

## Compliance workspace removed

Removed the admin/global Compliance workspace, the account Compliance evidence page, their imports and menu items, and the old workspace stylesheet. Remaining licence, prescription and recall forms now share `ReviewForms.css`. Settings and pharmacist dashboard links no longer point to removed pages. Old admin URLs redirect to the dashboard; global/account URLs redirect to their existing landing pages. Inspectors land on the protected product-recall view, and pharmacists can view their own licence at `/pharmacist/credentials`.

Application reviews remain in their respective management pages; recalls remain in Products & Stock. Shared backend records, professional verification endpoints and access checks were not deleted or disabled. No database data was changed. Production frontend build and diff checks passed. Browser verification confirmed `/admin/compliance` redirects to `/admin/dashboard` and that the sidebar no longer contains Compliance.

## Recall implementation retired

At the user's request, recall management has now been removed. Earlier recall-location notes are historical. The Products & Stock recall tab and component, operational recall APIs, notification dispatcher and queueing code, and Django admin recall registrations were removed. Old frontend recall URLs redirect to existing pages; old recall API endpoints return 404. The deprecated `view=recalls` query falls back to Items.

Future supply is controlled by product/SKU activation. `supply_error` explicitly rejects inactive items or inactive parent products, including at stock commitment for an existing order. Recall records no longer impose a supply hold. Product deactivation does not contact prior buyers or track recovery of already-sold stock. No actual product was deactivated as part of this code change.

The historical MedicineRecall and RecallAffectedOrder models/tables remain solely for preservation of past records, without live routes, admin actions, notification jobs or supply logic. No data-deletion migration was introduced. Locally both historical tables are empty.

Validation: 12 focused deactivation and flat-catalog tests passed, including blocked stock commitment without stock loss, a legacy active-child/inactive-parent case, retired endpoint checks and inert historical recall data. Frontend production build, Django checks and diff checks passed.
