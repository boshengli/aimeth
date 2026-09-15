# Publication and GitHub contract v0.1

This is a project quality standard. It is not a claim of current Science acceptance, exhaustive journal-policy compliance, or implemented production infrastructure.

## One formal result package

Every released result links:

`claim -> verification -> selected artifact -> source events -> frozen run -> protocol + task/model/code versions`

Required materials: a claim card; an immutable run manifest; original observable event/response/tool records; result table including unsuccessful runs; verifier evidence; analysis command/environment; figure source data; deviations and limitations; data/code availability statement. Large raw records are stored externally with checksums and access instructions. A checksum authenticates equality to a declared snapshot, not scientific truth or an independently trusted timestamp.

Claims distinguish known-result rediscovery, new validated lemma, unresolved construction, refuted proposal, and new theorem. State exact assumptions and all open proof obligations. Never fill a Results section with expected outcomes presented as observed findings.

## Article logic

| Section | Required content |
|---|---|
| Title / Abstract | Bounded empirical claim and system/task/model scope; no unsupported universality |
| Introduction | Research gap relative to agent scaling/organization work; hypotheses and discriminating predictions |
| Results | Budget-controlled organization comparison, verification quality, mechanism interventions, scale boundary, independent replication |
| Discussion | Alternatives, null/opposite effects, contamination, human contribution, external validity, practical limits |
| Methods | Tasks, units, randomization, models, roles/graphs, budgets, infrastructure, evaluator, statistics, exclusions, stopping |
| Supplement | Frozen prompts, graph policies, environment, provenance schema, failure catalogue, proof obligations, reproducibility commands |
| Availability / Contributions | Actual locations/access limits, licensing, author contributions, disclosed AI assistance, conflicts and funding |

Planned figures, **not generated results**: (1) experimental design and resource accounting; (2) verified success at matched budget with task/run uncertainty; (3) communication/verification interventions; (4) size-cost frontier; (5) traced mathematical case with failed branches. Each figure needs exact n and its unit, raw table, analysis commit, uncertainty definition and caption.

## Repository discipline

- Use small meaningful commits: problem/behavior, implementation, validation. Avoid manufactured “busy” histories. Preserve the commits actually used to run experiments.
- Use `codex/<purpose>` branches for work. PR text states the scientific/engineering issue, resulting behavior, relevant checks and limits. Initial local commit is not a GitHub PR or release.
- Use task-linked issues and decision records for protocol changes. No rewriting old experimental manifests; issue a new version with an explicit replacement link.
- CI runs inexpensive integrity/unit checks on every change. Cluster integration and proof builds have separate recorded environments and are not asserted by a green lightweight CI job.
- Put code, schemas/templates, analysis, small synthetic examples, source metadata and docs in Git. Keep credentials, model weights, full private traces, reference solutions and evaluation keys out of the public repository.
- Pin dependency versions and CI action revisions before a formal release. Store final environment locks/container digests, release manifest and checksums. Public release tags and persistent archives/DOIs follow actual release; do not fabricate them in templates.
- Maintain `CITATION.cff`, authorship, contributor roles, license, model/data redistribution rights and availability before public release. These decisions are currently unset; no blanket license is applied to supplied third-party material.
- Release acceptance includes a clean independent checkout/replay and a claim-evidence audit. Independent scientific review must use a fresh context and frozen inputs; reviewing one's own output is not independent confirmation.

## Current implementation boundary

This foundation includes templates, an executable source audit, a hash integrity verifier, regression tests, and a lightweight CI definition. It does not yet implement the full event schema, production scheduler, live telemetry, proof verification or statistical analysis. Those must be evidenced before a scientific-result release.
