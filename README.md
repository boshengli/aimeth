# AIMeth

[![Runtime and integrity checks](https://github.com/boshengli/aimeth/actions/workflows/checks.yml/badge.svg?branch=main)](https://github.com/boshengli/aimeth/actions/workflows/checks.yml)

**Agent organization and verifiable mathematical discovery under constrained compute.**

M1 established the research/evidence framework. M1.1 implements a durable single-host execution core: transactional events, fenced retries, atomic checkpoints and cross-round messages. M2 provides S/I/L/X organization baselines and a bounded institutional cluster calibration. No topology-superiority or frontier-proof claim is made.

## Try the runtime

Python 3.11+, standard library only. Run from this repository on local durable storage.

```bash
python3 -m aimeth_runtime --db runs/demo.sqlite demo demo --agents 4 --rounds 2
python3 -m aimeth_runtime --db runs/demo.sqlite verify demo
python3 -m unittest discover -s tests -v
```

The demo makes no model calls. Its policy and ring graph are engineering fixtures. [Runtime contract](docs/runtime-contract-v1.md) explains guarantees and limitations; [operations](docs/runtime-operations.md) covers restart, multi-process workers, backup, export and the optional local inference adapter. Multiple hosts must not write this SQLite database over a shared filesystem.

## Research and review

- [Research protocol v0.1](docs/research-protocol.md): proposed hypotheses, controls, independent population runs, evaluation and stopping rules.
- [Evidence audit](docs/evidence-audit.md) and [sources](references/sources.json): observed checks and source-reading boundaries.
- [Publication contract](docs/publication-contract.md) and [milestone policy](docs/milestone-reporting.md): traceable records and a readable HTML at every completed milestone.
- [M1 HTML](milestones/m1-foundation-v1.html), [M1.1 runtime HTML](milestones/m1-1-runtime-v1.html), and [M2 brief](docs/organization-design-brief.md).

The initial commit `934cce6` and original M1 report are retained. `archives/foundation-v1/` contains the exact initial Git tree; the original `foundation-manifest.json` is preserved byte-for-byte. Verify that historical snapshot with:

```bash
python3 tools/verify_artifacts.py archives/foundation-v1/foundation-manifest.json
python3 tools/verify_artifacts.py examples/replay/manifest.json
```

The root historical manifest describes the initial tree, not later README/runtime changes. Existing M1 report snapshots remain valid. All new milestones have separate evidence and content hashes.

## Scope

Passing integrity/fault tests does not verify a proof. Private databases, infrastructure identities, models, evaluator keys and credentials stay out of Git. Reviewed development traces are published with the gateway URL redacted. Seeds do not guarantee deterministic inference; retain realized requests, responses, schedules and software/model identities. Input-token admission, attributable GPU-hours, backend weight attestation and frontier-proof evaluation are outstanding.

Public repository: [boshengli/aimeth](https://github.com/boshengli/aimeth), published on 2026-09-16 with the original commit history and milestone tag. The [publication HTML](milestones/m1-1-publication-v1.html) and [observed hosted checks](https://github.com/boshengli/aimeth/actions/runs/35050227524) document that transition; earlier reports retain their original dates and status. A software license and DOI have not been assigned. Project administration remains in its separate registered control directory.

## M2.1 organization design and model-free tests

The [first M2 design](docs/organization-pilot-v1.md) adapts SLCW ideas from the user's Workflow project into four executable controls: serial S, independent I, local L and cross-group X. Hierarchy, adaptation, patterning and typed long-range routing are subsequent proposed ablations. [Math contracts](docs/math-evaluation-v1.md) distinguish exact development certificates from PDE and Navier–Stokes proof evaluation. The original M2.1 report is model-free; the subsequent live calibration is described below.

Run from the repository root with Python 3.9+ (validated on Python 3.11; standard library only):

```bash
python3 -m unittest discover -s tests -v
python3 -m aimeth_design compile --arm X --population 32 --output runs/my-pilot/manifest.json
python3 -m aimeth_design plan runs/my-pilot/manifest.json --prompt-token-cap 4096 --output runs/my-pilot/plan.json
python3 -m aimeth_design dry-run runs/my-pilot/manifest.json --db runs/my-pilot/run.sqlite --run-id my-pilot --output runs/my-pilot/trace.json
python3 tools/validate_design.py --output-dir runs/my-fresh-validation
```

Use a new output path for every invocation; no evidence file is overwritten. Dry-run can resume the same database/run with unchanged manifest, but write its summary to a new path. It rejects live transports. `compile --task <public-task.json>` freezes one object containing id and statement; `tasks/math-development-v1.json` is the task catalog, not a single task object. `evaluate --task-id <id> --candidate <certificate.json> --output <verdict.json>` performs the bounded exact check. Evaluator code and public test witnesses must be excluded from blinded generator mounts.

The selection seed is frozen before execution; changing it to cherry-pick a better terminal candidate is rejected. Selection v1 estimates a representative final agent, not best-of-N discovery. Call slots and maximum output ceilings are matched; total input tokens and GPU-hours are not. `plan` is arithmetic planning. The separate live pilot supervisor adds durable call/output reservations and bounded workers; full 10K production readiness remains unestablished.

M2.1 deliverable: [interactive HTML report](milestones/m2-1-organization-v1.html), [validation evidence](reports/m2-1-validation.json), and [public synthetic event chains](examples/organizations/traces). Run `python3 tools/check_organization_evidence.py` to verify their hash chains and configuration linkage.

## M2.1c institutional cluster calibration

[HTML report](milestones/m2-1-cluster-pilot-v2.html) · [frozen protocol and deviations](docs/cluster-pilot-v1.md) · [public results](reports/cluster-pilot-v1/v3/summary.json) · [all-attempt accounting](reports/cluster-pilot-v1/execution-audit.json).

Job 190043 completed the planned 32-population loop with 472 requests: 13 selected certificates passed, 9 were wrong, 4 malformed, and 6 populations stopped on truncated generation. N=8 for I/L/X, client concurrency <=2. Existing institutional model services were used; service names are not independently attested model weights. No direct public-provider API call was made. This is exploratory calibration on two public exact controls, not a frontier test, powered topology comparison, demonstrated two-node inference run or 10K inference launch.

The canceled routing trial and the complete v2 engineering-failed trial are retained and excluded from the organization comparison. Every request, response and peer message in v2/v3 is available in reviewed event exports; only the first-event gateway URL is redacted. Private SQLite snapshots verify in full; public replay verifies all subsequent event hashes, request/receipt hashes, terminal selection and exact certificate verdicts. First-event hash reconstruction requires the restricted original.

```bash
python3 tools/check_cluster_evidence.py
python3 tools/verify_artifacts.py cluster-report-v2-manifest.json
python3 tools/build_cluster_milestone_v2.py --output /tmp/cluster.html
cmp milestones/m2-1-cluster-pilot-v2.html /tmp/cluster.html
```

The optional cluster driver uses `python3 -m aimeth_pilot.run --config <private-config.json> --local-root <node-local-directory> --output-root <shared-output-directory>` inside `cluster/pilot.sbatch`. Credentials enter through `AIMETH_API_KEY`, not source files or prompts. Site paths and scheduling flags must come from the authorized project registry. Use a new immutable experiment directory after protocol changes; do not submit the old development manifests blindly.

Report v2 corrects v2-trial failure attribution (14 coordinator exits, 7 truncated-generation stops). The published v1 report and `cluster-report-manifest.json` remain unchanged and verifiable. V3 scientific outcomes are unchanged.
