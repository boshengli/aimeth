# P1 v2 · Mesoscopic domains from two-scale signalling — pre-run protocol

Written 2026-10-04 15:15 Asia/Shanghai, before the confirmatory tissue-scale run. Default direction taken
because the user had not chosen a mechanism (global plan, P1 tissue result T2/T3 not met). No language
model is called; no capability claim follows.

## Mechanism (added to `aimeth_dev/sim.py`, inactive by default; P1 v1 results reproduce bit-for-bit)

Each cell carries a domain-identity state D in [0, 1], inherited at division. Per step:
z = k_c (C - theta_c) + k_self (D - 0.5) + k_org EMIT_A - [two_scale only] k_l (L - theta_l),
D <- D + 0.3 (sigmoid(z) - D) + noise, where C and L are quasi-steady Gaussian fields of D over living
cells with ranges sigma_c = 3 and sigma_l = 25 cells. Organiser cells (EMIT_A) induce D; C is the
community effect (short-range positive feedback); L is long-range inhibition.

## Disclosure of exploration

Parameters (k_c 14, theta_c 0.45, k_self 4, k_org 8, k_l 10, sigma_c 3, sigma_l 25) were chosen during
exploration on a 300 x 300 lattice, 900 steps, seed 1 only: community alone took over the whole
population (100 % D), two_scale gave 7 domains of median 263 cells, k_l = 20 gave none, shuffled
signals gave none. Without k_org no domain nucleated. Parameters are frozen here; confirmatory seeds
11-15 were not used for tuning.

## Settings

Lattice 1,100 x 1,100; 5,000 steps; ceiling 1,000,000 cells; vectorised division; seeds 11-15.
Arms: v1_rules, community, two_scale, two_scale_L50 (sigma_l = 50), two_scale+shuffled,
two_scale+lesion (right half removed at step 4,000). Domain unit = 4-connected D-on component with
>= 100 cells. Spacing = Clark-Evans R of unit centroids vs 200 random-placement draws.

## Pre-specified predictions

| ID | Prediction | Criterion |
| --- | --- | --- |
| M1 | Two-scale signalling builds a tissue of many mesoscopic domains | two_scale >= 20 units in 5/5 seeds |
| M2 | Community effect alone runs away | community largest component >= 80 % of living cells in >= 4/5 |
| M3 | Spatial signal information is required | two_scale+shuffled: 0 units in 5/5 |
| M4 | Domains are regularly spaced | two_scale R above null 95th percentile in >= 4/5 |
| M5 | Domain size is set by the inhibitory range | median unit size two_scale_L50 >= 2.5 x two_scale in >= 4/5 paired seeds |
| M6 | Domains re-form after injury (exploratory) | two_scale+lesion units reported relative to intact; no claim |

A prediction not met is reported as not met; settings and criteria are not changed after the run.
