# Lab partner and laboratory — guided manual run

Date: 5 November 2026 (Africa/Nairobi). Tester: user; guide: Codex.
Environment: local website `http://localhost:3000`.
Status: not started. No records created or test results claimed by preparing this run.

The user operates the website. Work one step at a time, retaining the same partner and laboratory throughout. Use a separate browser profile/window for each role so admin and partner sessions do not replace each other. Use clearly labelled synthetic documents and details in the local test environment; actual inbox delivery and any external credential verification require their own evidence. Keep passwords and activation tokens out of the record below.

## Reference sheet

| Item | Reference / value |
|---|---|
| Partner organisation | MANUAL Lab Partner 0511 |
| Partner email | Tester to choose an unused email they can access |
| Partner application ID/reference | |
| Partner account ID / activation result | |
| Laboratory name | MANUAL Laboratory 0511 |
| Facility ID/reference | |
| Offered test / facility price | |
| Technician account / facility assignment | |
| Customer lab request reference | |
| Result reference / download evidence | |

## Ordered checks

- [ ] L01: Open professional registration in a separate browser profile, select **Lab Partner**, and continue. Expected: organisation/contact form, not the doctor form. Current step; awaiting user observation.
- [ ] L02: Try continuing with required organisation/contact fields empty. Expected: clear field errors and no application created. Fill valid synthetic organisation/contact details using an unused accessible email.
- [ ] L03: Complete eligibility/quality information and required document uploads. Exercise one invalid upload, then correct it. Expected: valid files remain selected; errors identify the invalid file. Only the tester can accept required declarations/terms.
- [ ] L04: Submit once. Expected: saved application reference and pending-review state. Refresh; inspect confirmation in the configured test mailbox/inbox. A submission message alone does not establish external email delivery.
- [ ] L05: In the admin session, open Laboratory Operations → Applications. Expected: exactly one partner application with matching organisation, contact and documents. The pending partner cannot receive patient requests.
- [ ] L06: Request missing information on this application if supported, then provide it as partner and confirm the review trail. Approve/provision the completed application through the website.
- [ ] L07: Receive/open the activation invitation and set the password yourself. Expected: partner login succeeds and opens the lab dashboard. Reusing the activation link is rejected. Record a missing invitation or inaccessible mailbox as blocked.
- [ ] L08: As the partner, register **MANUAL Laboratory 0511** with its address, county, contact, licence number/expiry and synthetic facility document; configure an offered test and its price where provided. Expected: one saved facility pending Ava verification; partner approval does not automatically verify the facility.
- [ ] L09: In admin Laboratory Operations → Applications, review that laboratory under the correct legal partner and verify it. Expected: matching facility details/documents, retained review history and verified state in the partner dashboard.
- [ ] L10: Add/activate a test technician through the available workflow and assign them to this verified facility. Expected: correct partner/facility membership; a technician from another partner cannot be assigned.
- [ ] L11: Confirm the offered test, facility price and collection availability in the customer lab catalog. Pending/suspended facilities must remain unavailable. Record database KPI totals before and after creation; table search/pagination must not change them.
- [ ] L12: As customer, book one synthetic lab request at this laboratory. Expected: correct patient, facility, test, quote and supported payment arrangement. Record the request reference; do not assume online payment is offered.
- [ ] L13: Assign collection/processing to the technician. For home collection, reject one wrong collection code, then verify the correct code. Expected: no premature sample collection and no successful code reuse.
- [ ] L14: Progress through sample collected → processing → result ready using the offered workflow. Upload a clearly synthetic result and complete the request. Expected: correct request association, permitted transitions and actor/timestamp history.
- [ ] L15: As the customer, open the notification and download the matching result. Confirm another customer and unrelated technician cannot access it. Verify the final request and facility views agree across all roles.

## Results and issues

| Step | Result: Pass / Fail / Blocked / Not tested | Observed result / reference | Issue / retest |
|---|---|---|---|
| L01 | Not tested | Awaiting user | |

Do not tick a step until the user performs it and reports the expected visible result. On failure, retain the message/reference, fix or investigate it, and retest before continuing dependent steps. This run is functional QA, not verification of genuine professional credentials.
