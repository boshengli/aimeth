# Human-readable milestone reports

- [M1 v1.0 — Research foundation](m1-foundation-v1.html): requirement mapping, evidence, prototype limitations, and M2 organization-design readiness.

Every completed milestone requires an HTML report under [the milestone reporting policy](../docs/milestone-reporting.md).

Rebuild M1 from the repository root using Python 3.11+:

```bash
python3 -B tools/build_milestone.py
python3 -B tools/verify_artifacts.py milestones/m1-foundation-v1.manifest.json
```

M1 preserves the original foundation files and hashes. It adds a report, evidence snapshot and design brief; it does not rewrite the original study protocol or invent experimental results. `m1-foundation-v1.clean-checkout.json` records the previous baseline clone check on the same machine, not an independent scientific review.

Optional browser QA uses Node.js and Playwright, separate from the standard-library core tools. With Playwright and its Chromium browser available:

```bash
node tools/check_milestone_browser.cjs milestones/m1-foundation-v1.html /path/to/qa-output
```

`AIMETH_BROWSER_EXECUTABLE` can select an installed Chrome executable. The checker starts an isolated temporary profile and blocks HTTP(S) resource requests. It checks four diagram states, matched graph degrees, desktop/tablet/mobile overflow, evidence disclosure, print wiring, and JavaScript-disabled core content. Screenshots need human/visual inspection; a passing script alone does not judge editorial quality.
