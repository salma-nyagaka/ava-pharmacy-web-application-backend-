# Manual end-user checklist

Open [the interactive checklist](index.html) in a browser, or read [the Markdown guide](../../docs/manual-end-user-testing-guide.md).

- 56 cases, 356 numbered actions, 8 final sign-off checks.
- Each action includes an expected result. All 110 original acceptance scenarios have a coverage mapping.
- Browser progress, case outcomes, notes and run fields save locally; export JSON to back up or transfer results. Import restores a prior export. Print / Save PDF prints the current checklist including notes and run details.
- Desktop, phone, customer, staff handoffs, invalid inputs, privacy checks and known integration limits are covered.
- Default run is blank. Testing the guide did not execute product workflows, send payment prompts or modify application records.

Validation: unique case/step IDs, 110/110 scenario coverage, existing local links, browser rendering, blank initial state and reload persistence checked. Temporary verification entries were removed. Print styles are supplied; no PDF artifact was generated. Export/import controls are supplied; file round-trip has not been independently exercised.

Rebuild: run `python3 scripts/build_manual_testing_guide.py` from the backend workspace after editing the Markdown source. Run locally with `python3 -m http.server 8045 --bind 127.0.0.1` from the workspace, then visit `http://127.0.0.1:8045/output/manual-testing/index.html`.
