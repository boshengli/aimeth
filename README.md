# AIMeth

[![Runtime and integrity checks](https://github.com/boshengli/aimeth/actions/workflows/checks.yml/badge.svg?branch=main)](https://github.com/boshengli/aimeth/actions/workflows/checks.yml)

**Agent organization and verifiable mathematical discovery under constrained compute.**

M1 established the research/evidence framework. M1.1 implements a durable single-host execution core: transactional events, fenced retries, atomic checkpoints and cross-round messages. M2 organization design is next; no topology-superiority claim, live cluster experiment or independently verified mathematical proof is included.

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

Passing integrity/fault tests does not verify a proof. Production database/trace archives, models, evaluator keys and credentials stay out of Git. Seeds do not guarantee deterministic inference; retain realized requests, responses, schedules and software/model identities. Whole-run compute accounting, real H20 deployment and proof/evaluator integration are outstanding.

Public repository: [boshengli/aimeth](https://github.com/boshengli/aimeth), published on 2026-09-16 with the original commit history and milestone tag. The [publication HTML](milestones/m1-1-publication-v1.html) and [observed hosted checks](https://github.com/boshengli/aimeth/actions/runs/35050227524) document that transition; earlier reports retain their original dates and status. A software license and DOI have not been assigned. Project administration remains in its separate registered control directory.
