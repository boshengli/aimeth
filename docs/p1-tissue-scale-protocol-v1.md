# P1 tissue-scale extension — pre-run protocol v1

Written 2026-10-04 before the first tissue-scale run. Same genome, rules and
parameters as P1 v1 except the settings below. Exploratory; no language model
is called; no capability claim follows.

## Question

At the user's proposed tissue scale (10^5-10^6 cells), does the same local
development form a tissue made of many mesoscopic units (organiser domains),
with regular spacing, bounded large-model cost and retained task placement?

## Settings

- Lattice 1,100 x 1,100; 5,000 steps; living-cell ceiling 1,000,000.
- Vectorised division (one random neighbour per attempt; conflicts resolved by random priority). This differs from P1 v1's sequential rule and is a new condition, not a replicate.
- Arms: full, shuffled_signal, task_blind, full+lesion (right half removed at step 4,000).
- Seeds 1-5 per arm; one population run is the independent unit.
- Mesoscopic unit: 4-connected component of interior activator-on cells, size >= 3.
- Spacing: Clark-Evans R of unit centroids; null = same number of points on random living cells (200 draws).
- Hardware: GPU08 CPUs only (no GPU), conda env /data/libs/aimeth/envs/dev.

## Pre-specified expectations

| ID | Expectation | Criterion |
| --- | --- | --- |
| T1 | Signalling still required | full organiser z > 3 in 5/5 seeds; shuffled_signal z < 1 in 5/5 |
| T2 | Tissue of many units | full >= 20 mesoscopic units in 5/5 seeds |
| T3 | Units regularly spaced | full R above the 95th percentile of its null in >= 4/5 seeds |
| T4 | Cost bounded at scale | full large-model calls <= 5 per 1,000 cell-steps in 5/5 seeds |
| T5 | Task placement retained | demand coverage full > task_blind in 5/5 paired seeds |
| T6 | Regeneration (exploratory) | full+lesion final cells >= 80% of intact full (reported, no claim) |

## Disclosure before submission

A smoke test (lattice 300, 600 steps, seed 1) was run before submission to
check the code path. It gave 47 units with R = 0.80 against a null mean of
1.19, i.e. clustered rather than regular spacing. T3 is kept unchanged as the
pre-specified prediction; this disclosure is recorded so that a T3 failure is
not presented as a surprise or reinterpreted afterwards.
