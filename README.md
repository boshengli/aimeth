# AIMeth

**Agent organization and verifiable mathematical discovery under constrained compute.**

Status: research foundation, 2026-09-14. No cluster experiment, topology superiority claim, or independent Navier–Stokes proof verification is included in this release.

## Read first

- [Research protocol v0.1](docs/research-protocol.md) — hypotheses, controls, experimental units, budgets, evaluation, and decision gates.
- [Evidence and prototype audit](docs/evidence-audit.md) — sources, actual checks, limitations.
- [Engineering contract](docs/engineering-contract.md) — required behavior for the future runner.
- [Publication and GitHub contract](docs/publication-contract.md) — reviewable results and release requirements.
- [Source registry](references/sources.json) — URLs, dates, scope of inspection.

## Local checks

Python 3.11 or later; the tools in this foundation use only the standard library.

```bash
python3 -m unittest discover -s tests -v
python3 tools/verify_artifacts.py examples/replay/manifest.json
python3 tools/audit_handoff.py --source /path/to/H20_10K_Navier_Handoff_20260914 --output /path/to/audit.json
```

The example is synthetic integrity-test data, not mathematical or cluster evidence. The artifact verifier validates declared file identities and hashes only; it does not validate mathematical correctness or completeness of an experiment. The handoff audit parses source and uses local mocks; it never submits jobs or makes model requests.

## Boundaries

The supplied handoff is retained externally as an unchanged source package, not installed as an operational skill. Its scripts are not yet production-ready. Reference solutions must never be mounted in a generator environment. This repository is a research/control foundation, not a deployed 10K-agent runner.

Project administration lives in the separate `0023-AIMeth` iCloud control directory. Large traces, model files, evaluation keys, and credentials stay outside Git. No GitHub remote, public release, DOI, or project license has been assigned yet.
