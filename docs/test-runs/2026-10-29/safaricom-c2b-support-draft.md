# Draft: Daraja sandbox C2B callback non-delivery and intermittent registration failure

To: apisupport@safaricom.co.ke

Subject: Sandbox C2B callbacks not delivered — avapharmacy-test / shortcode 600980

Hello Daraja support,

We are testing C2B Paybill on sandbox app `avapharmacy-test`, using the C2B simulator's shortcode **600980** and virtual test phone **254708374149**. STK uses the separate sandbox shortcode 174379.

Registration and simulations have returned successful API responses, but no confirmation callback has reached our callback gateway and no M-Pesa transaction receipt has been received. Registration also intermittently returns HTTP 500 / `500.003.1001`, with the message “Service is currently unreachable. Please try again later.”

Relevant provider request/conversation IDs:

- Successful v2 registration: **8e77-4dec-98af-2e0707a6447d379927**, ResponseCode `00000000`, ResponseDescription `Success`.
- Accepted v2 simulation: **135b-4679-8ea6-1c3dca88c6a4373851**, ResponseCode `0`.
- Latest failed original-format registration: **135b-4679-8ea6-1c3dca88c6a4377025**, HTTP 500 / `500.003.1001`.
- Alternate-format v2 registration failure: **135b-4679-8ea6-1c3dca88c6a4376484**.
- Alternate-format v1 registration failure: **135b-4679-8ea6-1c3dca88c6a4376711**.

The accepted KSh 1 simulation used BillRefNumber **AVA-ORD-20CDFB9E**. An incorrect-amount test used **AVA-ORD-874A0705** (order expects KSh 2; simulation amount KSh 1), and an unmatched-reference test used **QA-NOMATCH-A9D827**. These are synthetic QA references, with no real patient information.

The sandbox callback host is **ac3f-41-79-237-222.ngrok-free.app**. The gateway is publicly reachable over HTTPS, exposes only the intended callback routes and rejects unsigned requests. An authenticated validation probe reaches the backend and correctly rejects an unknown account reference. We have preserved secret authentication throughout the tests. The actual credential-bearing URLs can be identified from the accepted registration request; credentials are omitted from this draft.

Could you please check:

1. Whether the successful registration was stored for shortcode 600980 and this app.
2. Whether the accepted simulation generated a C2B transaction and outbound callback attempt, including the destination and delivery result.
3. Whether there is a restriction on temporary ngrok-free callback hosts or authenticated callback URLs in sandbox, and the supported alternative if so.
4. Why registration alternates between success and HTTP 500 for these requests.

Thank you.
