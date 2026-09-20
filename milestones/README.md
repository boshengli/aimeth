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

## M1.1 — Durable runtime, local engineering report

[M1.1 v1.0 HTML](m1-1-runtime-v1.html) records transactional events, recovery and cross-round messages. Public GitHub publication remains pending owner identification in this snapshot.

```bash
python3 tools/build_runtime_milestone.py
python3 tools/verify_artifacts.py runtime-report-manifest.json
node tools/check_runtime_milestone.cjs milestones/m1-1-runtime-v1.html /path/to/qa.json
```

The builder checks the frozen `archives/runtime-v0.1/aimeth_runtime` snapshot, derived exactly from commit `313b85f`, so later runtime edits do not rewrite this report. The report manifest covers its immutable inputs/outputs; current code evolves in later commits. Live databases and large synthetic stress traces stay in ignored `runs/`; small synthetic examples and all load summaries are retained for review.

## M1.1 publication supplement — 2026-09-16

[Public GitHub release record v1.0](m1-1-publication-v1.html) records the confirmed owner, anonymous public access, retained initial history and successful hosted checks. This supplements the preserved local report rather than rewriting it.

```bash
python3 tools/build_publication_milestone.py
python3 tools/verify_artifacts.py publication-report-manifest.json
node tools/check_publication_milestone.cjs milestones/m1-1-publication-v1.html /path/to/qa.json
```

The report cites the published, tested source baseline; its own delivery is a later Git commit. Final delivery-head CI is linked in the project handoff, avoiding a self-referential report hash.

## M2.1c — Institutional cluster calibration

[Cluster calibration HTML](m2-1-cluster-pilot-v2.html) retains all four jobs, failures, mathematical verdicts and readiness limits. Public data are reviewed live development traces, with only the first-event gateway URL redacted. The execution source is frozen under `archives/cluster-pilot-v1`; future evaluator changes must not silently reclassify this report.

```bash
python3 tools/check_cluster_evidence.py
python3 tools/build_cluster_milestone_v2.py
python3 tools/verify_artifacts.py cluster-report-v2-manifest.json
node tools/check_cluster_milestone_v2.cjs milestones/m2-1-cluster-pilot-v2.html milestones/m2-1-cluster-pilot-v2.browser-qa.json
```

Report v2 corrects v2-trial failure attribution (14 coordinator exits, 7 truncated-generation stops). The published v1 report and `cluster-report-manifest.json` remain unchanged and verifiable. V3 scientific outcomes are unchanged.

## M2.1d — Service and output calibration

[Service calibration HTML v1](m2-1-service-calibration-v1.html) separates 48 institutional one-step cases from 8 post-observation public API diagnostics. It records metadata identity limits, all certificate failures, an exact scaling-algebra control and the unimplemented H/F design proposal.

```bash
python3 tools/check_service_evidence.py
python3 tools/check_public_sanity.py
python3 tools/build_service_milestone.py
python3 tools/verify_artifacts.py service-calibration-report-manifest.json
node tools/check_service_milestone.cjs milestones/m2-1-service-calibration-v1.html /path/to/browser-qa.json
```

Execution archives are `archives/service-calibration-v1` (a03dad6) and `archives/public-sanity-v1` (7211541). They are separate from the later report delivery commit. Browser screenshots and source-backed evidence accompany the HTML. This milestone does not establish population superiority, frontier proof or 10K inference readiness.

## M2.2 — Matched role-routing runtime and live pilot

[HTML v1](m2-2-role-routing-v1.html) includes all 16 planned populations, 16 prior representation cases, a separate gateway diagnosis and post-pilot compact prompt storage. GLM started eight populations; DeepSeek's eight remain unstarted after 502 failures. The report separates engineering execution, output-contract failures and mathematical certificate outcomes.

Replay with `python3 tools/check_role_evidence.py`; rebuild with `python3 tools/build_role_milestone.py`; verify `role-pilot-report-manifest.json`. Browser QA and screenshots cover desktop, narrow layouts, filters including unstarted units, horizontal table scrolling, offline/no-JS reading and printing the complete planned denominator.
