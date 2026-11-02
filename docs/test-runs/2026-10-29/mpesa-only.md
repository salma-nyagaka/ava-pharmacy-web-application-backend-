# M-Pesa-only payment policy — 29 October 2026

The user confirmed **M-Pesa only: no card payments and no cash on delivery**. Supported checkout channels are **M-Pesa STK Push** and **M-Pesa Paybill**. Flutterwave setup and its outstanding webhook URL update are no longer required work.

## Implemented

- Checkout serializers accept only `mpesa_stk` and `mpesa_paybill`. Customer payment-intent creation accepts only `mpesa` and `paybill`; card and manual-paid requests are rejected.
- Dedicated card initiation returns **410 Gone** before contacting Flutterwave. New M-Pesa payments and checkout finalization also reject historical card/COD orders.
- New orders default to M-Pesa STK, via applied migration `0013_mpesa_default`. Historical card/COD values are retained, not rewritten.
- Django admin offers only M-Pesa methods for new orders. Existing order payment methods remain read-only. Fulfillment requires confirmed payment, including for legacy COD records.
- Storefront checkout no longer restores card payment state from old callback URLs. Historical unsupported orders show a message to start a new M-Pesa checkout.
- Account payment methods now present only M-Pesa numbers. Card entry/expiry/CVV fields and type selection were removed. The backend rejects new or updated card entries; existing records remain retained for history.
- The public callback gateway now forwards only the three authenticated M-Pesa callback routes. Card callback and card-return routes are no longer forwarded.
- Historical card payment records and read/reconciliation logic remain available; no financial history or previous test evidence was deleted.

## Validation

- **201 tests passed** across accounts, catalog/inventory and orders: [backend log](mpesa-only/backend-tests.log).
- **3 gateway tests passed:** [gateway log](mpesa-only/gateway-tests.log).
- Frontend production build passed: [build log](mpesa-only/frontend-build.log).
- Payment-policy tests cover supported M-Pesa channels, rejected card/COD checkout, rejected card/manual intents, disabled card initiation without a provider call, legacy order read access with blocked finalization, saved M-Pesa references, rejected saved cards, and admin restrictions.
- Existing stock, prescription and notification tests now use explicitly simulated confirmed M-Pesa payment fixtures before finalization/fulfillment. These fixtures do not constitute live provider payment proof.
- Browser: the account form offers only account name and M-Pesa phone number, with no card fields. [Screenshot](mpesa-only/payment-methods.png).
- Browser: opening historical card order 1996 through checkout shows **“This order uses a payment method that is no longer supported. Start a new M-Pesa checkout.”** It does not restore a card checkout. [Screenshot](mpesa-only/legacy-checkout-blocked.png).

## Checklist scope

Orders now has **13 passed application scenarios, 2 N/A scenarios, and 3 blocked integrations**. ORD-07 (card) and ORD-08 (cash on delivery) are N/A by the user's explicit policy. Their rejection checks pass.

ORD-05 still requires successful Safaricom sandbox STK confirmation; previous queries were rate-limited. ORD-06 still requires successful Paybill registration/payment; previous registration returned provider HTTP 500. ORD-14 remains blocked because no POS provider has been selected. None of these blockers requires Flutterwave setup.
