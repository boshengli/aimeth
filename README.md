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

## M2.1d service identity and output-contract calibration

[HTML report](milestones/m2-1-service-calibration-v1.html) · [frozen calibration](docs/service-calibration-v1.md) · [separate public API diagnostic](docs/public-sanity-v1.md) · [H/F routing proposal](docs/hierarchy-routing-proposal-v1.md).

Institutional job 190045 ran 48 one-step cases: 18 exact certificates passed, 21 were wrong, 8 malformed, and 1 truncated; 18,256 reported tokens. These are output-contract diagnostics, not population organization comparisons. After all 16 local antiderivative cases failed, a separately frozen 8-call official DeepSeek/GLM diagnostic produced 2 passes and 6 invalid certificates (2,033 tokens). The model versions differ, so these data cannot identify deployment quality or rank model families.

Read-only job 190044 preserved configuration/tokenizer hashes and shard sizes for four model directories. Weight bytes, gateway routes and two-node inference participation remain unattested. The new Navier–Stokes scaling control checks exact exponent equations, not a PDE proof or regularity. H/F role-routing graphs are degree-matched proposals; their runtime and live comparison are not implemented.

```bash
python3 tools/check_service_evidence.py
python3 tools/check_public_sanity.py
python3 tools/verify_artifacts.py service-calibration-report-manifest.json
python3 tools/build_service_milestone.py --output /tmp/service.html
cmp milestones/m2-1-service-calibration-v1.html /tmp/service.html
```

Both execution sources and all reviewed development events are archived separately. Old reports remain unchanged. Input-token admission, role-message contracts, independently reviewed harder tasks and identity attestation precede the next organization pilot and scale-up.

## M2.2 matched role routing and institutional results

[Milestone HTML](milestones/m2-2-role-routing-v1.html) · [frozen live protocol](docs/role-routing-pilot-v1.md) · [all results](reports/role-pilot-v1/summary.json).

Job 196060 implemented role-bound H/F routing with N=8 and four rounds. GLM met the predeclared format gate and started eight populations: one passed, one invalid certificate, four malformed final outputs and two truncated populations. DeepSeek returned HTTP 502 in all eight representation cases; its eight planned populations remain unstarted. A separately frozen minimal operational probe returned the gateway message `backend unavailable / Connection refused`. No service configuration was changed.

The institutional job made 224 requests, with 195,352 known tokens and eight unknown-usage failures. The separate gateway probe adds one request with unknown usage. All 24 journals, 1,539 public events, 197 sent messages and frozen selection/score rules are retained. These public development controls and two repeats do not support architecture superiority, a frontier proof or independently attested GPU01 routing.

A post-pilot engineering increment replaces per-agent prompt copies with four role templates. The eight first-round H requests are byte-identical to the executed version. H/F N=10000 manifests now compile at 1,238,453 bytes; this is not 10K inference, and the live driver remains deliberately fixed to N=8. The executed source (8712fd9), gateway diagnosis (70a67c2), and compact implementation (b955936) have separate archives. Hard request-byte/output/call limits are enforced; tokenizer-derived input admission, GPU-hour attribution and multi-host recovery remain open.

```bash
python3 tools/check_role_evidence.py
python3 tools/verify_artifacts.py role-pilot-report-manifest.json
python3 tools/build_role_milestone.py --output /tmp/role.html
cmp milestones/m2-2-role-routing-v1.html /tmp/role.html
python3 tools/validate_role_scale.py --output runs/a-new-scale-check.json
```

## M2.3 four-role output-contract calibration

[Milestone HTML](milestones/m2-3-role-contract-v1.html) · [v1 protocol](docs/role-contract-calibration-v1.md) · [v2 continuation](docs/role-contract-calibration-v2.md).

After the M2.2 format failures, a separately frozen one-step calibration compares the old prompt with a final output card across four roles, two tasks, empty/archived contexts and two repeats. V1's DeepSeek transport error and GLM short-probe truncation are preserved with all 128 unstarted cells. A new frozen GLM-only v2 executed 64 requests: format validity rose from 15/32 to 25/32, with 14 card-only and four baseline-only valid pairs. The predeclared 32/32 readiness gate failed. All mathematical passes (6/32 vs 15/32) came from the prime control; NS scaling algebra passed 0/16 in both arms.

Combined records retain 66 requests, 59,177 known tokens, one unknown-usage attempt, 524 events and both execution archives. Shared historical contexts and repeated tasks are dependent observations. These are developmental format results, not a new population comparison or frontier proof; token costs differ. GPU08 use is authorized, but scheduler admission and independently attested model serving remain open.

```bash
python3 tools/check_contract_evidence.py --batch v1
python3 tools/check_contract_evidence.py --batch v2
python3 tools/verify_artifacts.py role-contract-report-manifest.json
python3 tools/build_contract_milestone.py --output /tmp/contract.html
cmp milestones/m2-3-role-contract-v1.html /tmp/contract.html
```

## M2.4a GPU08 restoration assessment

[HTML assessment](milestones/m2-4a-gpu08-restoration-v1.html) · [observed evidence](reports/gpu08-restoration-v1/evidence.json).

The existing eight-GPU allocation was preserved. A read-only audit found no basecalling or model-serving process for the project user and confirmed the original model directories and current mounts. Under a valid CPU job, the same credentials successfully logged in and were adopted into that job; no GPUs were exposed. This establishes the own-job SSH requirement, not restored eight-GPU access or the exact pre-loan state. No unknown job, existing service, mount or shared data was changed. A legitimate GPU allocation/execution path is still required before new model loading.
