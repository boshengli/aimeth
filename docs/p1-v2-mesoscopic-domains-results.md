# P1 v2 · Mesoscopic domains from two-scale signalling — results

Run 2026-10-04 15:20–17:22 Asia/Shanghai on GPU08 (Slurm job 239978, 30 processes), exactly as frozen in
`docs/p1-v2-mesoscopic-domains-protocol.md` (lattice 1,100 × 1,100, 5,000 steps, seeds 11–15, six arms, domain unit =
4-connected domain-on component ≥ 100 cells). No language model is called; no capability claim follows.
Records: `/data/libs/aimeth/p1-v2-domains/out`; evaluation: `tools/summarize_tissue_v2.py` → `reports/p1-v2/summary.json`.

## Pre-specified predictions

| ID | Criterion | Per seed (11–15) | Verdict |
| --- | --- | --- | --- |
| M1 | two_scale ≥ 20 units in 5/5 | 20, 19, 21, 17, 18 units | **not met** (2/5) |
| M2 | community largest component ≥ 80 % in ≥ 4/5 | 100 % in 5/5 | **met** |
| M3 | two_scale+shuffled 0 units in 5/5 | 0 in 5/5 | **met** |
| M4 | two_scale Clark–Evans R above null 95th percentile in ≥ 4/5 | R 1.14–1.35 vs null p95 1.52–1.59 | **not met** (0/5) |
| M5 | median unit size L50 ≥ 2.5 × two_scale in ≥ 4/5 | ratios 1.49, 1.62, 1.91, 2.36, 2.22 | **not met** (0/5; direction 5/5) |
| M6 | lesion units relative to intact (exploratory) | 1.20, 1.05, 0.95, 1.65, 1.56 | reported, no claim |

Other read-outs: domain-on fraction 8.3–8.6 % (two_scale), 10.3–10.4 % (L50); median unit size 122–143 cells (two_scale),
213–316 (L50); L50 gave more units (33–42) than two_scale (17–21). v1 rules: 0 units. Population ≈ 378–381 k cells per seed;
the domain state does not feed back on growth, so arms sharing a seed have identical cell counts.

## What the tissue looks like (seed 11, `reports/p1-v2/p1v2_domains_seed11.png`)

The units that pass the 100-cell threshold sit almost entirely on the **tissue margin**; the interior carries only scattered
domain-on single cells. After the right half is removed at step 4,000, new units form along the **cut surface**. So the
mechanism, as frozen, makes signal-dependent, size-limited domains (M2, M3) but not an interior array of regularly spaced
domains (M1, M4), and the inhibitory range moves size in the predicted direction but by less than pre-specified (M5).

## Reading

* The pre-specified picture ("a tissue of many mesoscopic domains") is not supported by this mechanism and these parameters.
* Margin- and wound-localised domain formation is the visible behaviour. It is reminiscent of regeneration starting at cut
  surfaces, but it is a property of this model that has not been analysed yet (candidate causes: organiser-gene placement
  at the growth front, inheritance of the domain state at division, field asymmetry at the boundary); it is not evidence
  about callus biology.
* The parameters were tuned on one 300 × 300 seed; at 1,100 × 1,100 the domain count per area is far lower than in tuning.
  Any re-tuning is exploratory and needs new confirmatory seeds.

## Next (not started)

1. Diagnose margin localisation (map EMIT_A and D against distance to the margin; rerun one seed with a no-growth interior
   control). 2. If an interior lattice is still wanted, freeze a v3 protocol before running new seeds.
