# P1 offline developmental simulator — pre-run protocol v1

Written 2026-10-04 before the first full run. Exploratory engineering
milestone of the two-tier cell-cost design (AIMeth global plan v2, P1).
No language model is called; no capability claim follows from P1.

## Question

Can lightweight cells, regulated only by local signals and a shared
six-gene genome, (a) form self-organised structure that a signal-shuffle
control cannot, (b) keep the expensive large-model gene rare, (c) place
work where the task demands it, and (d) regenerate after injury better
than a fixed, non-dividing population?

## Fixed settings

- Lattice 96 x 96, 300 steps, living-cell ceiling 5,000, seed founder disk radius 2.
- Genes: GROW, EMIT_A, EMIT_I, BORDER, WORK, EXPENSIVE (see `aimeth_dev/sim.py`).
- Large-model calls are event-triggered: a cell whose EXPENSIVE expression exceeds 0.5 fires at most once per 30 steps.
- Ten independently seeded populations per condition (seeds 1-10); a population run is the independent unit.
- Fixed-population control: 3,000 cells placed at step 0, no division.
- Lesion: at step 200 every living cell right of the population centroid is removed.
- Permutation nulls: 200 label shuffles within the same living cells.

## Conditions

full · shuffled_signal · fixed_population · frozen_expression · task_blind;
plus lesion variants full+lesion and fixed_population+lesion.

## Pre-specified expectations and criteria

| ID | Expectation | Criterion |
| --- | --- | --- |
| E1 | Signalling creates organiser centres | organiser clustering z (interior activator-on cells) in full > 3 in at least 8/10 seeds, and shuffled_signal median z < 1 |
| E2 | Expensive gene stays rare | full: expensive calls <= 50 per 1,000 cell-steps (<= 5% of a "every cell calls the model every step" design) |
| E3 | Task conditioning places work | demand coverage full > task_blind in at least 8/10 paired seeds |
| E4 | Development regenerates | full+lesion final cells >= 80% of intact full; fixed_population+lesion final cells < 60% of intact fixed_population |

A criterion not met is reported as not met. Criteria and settings are not
changed after seeing results; any later change is a new protocol version.
