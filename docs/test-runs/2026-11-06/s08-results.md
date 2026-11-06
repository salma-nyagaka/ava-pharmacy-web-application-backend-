# S08 checks — 6 November 2026

Executed 10 focused backend tests against an isolated in-memory SQLite database using the current models (migrations disabled). All 10 passed. This is API/service verification, not a completed browser acceptance run or a PostgreSQL concurrency/migration test. No live customer orders, stock, support tickets, or provider refunds were changed.

The stock/review fixture was updated for the flat catalog: A and B now belong to separate exact sellable products. The review check fetches each product by its product ID.

| Check | Evidence and limits |
| --- | --- |
| S08-04 | Stock commit and repeated commit: A/store 1 50 → 48; A/store 2 stays 30; B/store 1 stays 20; B/store 2 stays 10. Repeated release returns only A/store 1 to 50. Paid checkout/finalize also passes. The current model has no separate reserved-stock quantity; available_quantity is stock plus any backorder allowance. A reserved/available split cannot be marked verified. |
| S08-05 | Electronic receipt is sent once; finance CSV checks the matching order number, total and payment status. Visual customer receipt/admin invoice comparison for one live order remains pending. |
| S08-06 | Customer review saves to the purchased exact variant; the other product retains zero reviews. Ownership and rating validation pass. Browser display/moderation remains a manual check. |
| S08-07 | Paid checkout cancellation restores stock once; repeated cancellation is rejected. Unpaid cancellation does not move stock. |
| S08-08 | Customer return API creates a persisted ReturnRequest ID attached to the URL order; ownership is protected. This is a database ID, not a new formatted return reference. |
| S08-09 | Staff cannot mark a return received without quarantine and non-resale acknowledgements. Connected return/refund test leaves saleable stock unchanged. Physical quarantine remains a staff action. |
| S08-10 | Synthetic refund recording is idempotent and agrees with the finance export. No actual external refund or real provider reference was supplied or verified; live reconciliation remains pending. |
| S08-11 | Synthetic order-linked support ticket is created, updated by staff, resolved after the simulated refund record, and readable by its customer. No real support issue was closed. |

## Executed tests

- products ModuleAcceptanceTests: two_pack_sale_and_repeated_commit_release_keep_exact_balances; inv02_paid_checkout_deducts_exact_store_and_cancellation_restores_once; reviews_target_exact_variant_and_enforce_purchase_ownership.
- orders OrdersModuleAcceptanceTests: order_scoped_return_uses_url_order_and_protects_ownership; return_review_requires_quarantine_and_recorded_refund; delivered_refund_does_not_restock_and_replay_has_one_event; finance_csv_matches_order_and_is_staff_only.
- orders ConnectedRecoveryTests: failed_payment_retry_return_refund_and_support; unpaid_cancellation_never_moves_stock_and_cannot_be_finalized.
- orders MpesaFlowTests: paid_mpesa_order_sends_one_electronic_receipt.

The payment_failed log entry is the deliberately simulated first failed payment in the retry test; the suite passed.
