# Mathematical task and evaluation contracts · M2.1

The public development controls in `tasks/math-development-v1.json` have machine-checkable certificates, not a general proof rubric. Evaluator implementation is in `aimeth_evaluation/`; never mount it or the test fixtures into a blinded generator. These controls and witnesses are public and intentionally unsuitable for held-out evaluation.

## Draft PDE bridge contracts (not expert-approved or executed)

- **PDE-E1, energy identity.** For a smooth divergence-free solution on the three-dimensional unit torus, positive viscosity and smooth forcing on a fixed time interval, derive the differential L2 energy identity. Verify periodic integration by parts, cancellation of transport and pressure, viscosity sign, forcing pairing and all regularity assumptions. A natural-language checker is not supplied.
- **PDE-E2, missing norm control.** Determine whether a uniform L2 bound on arbitrary smooth vector fields on R3 implies a uniform L-infinity bound; require an explicitly quantified family and exact norm analysis. Distinguish arbitrary fields from actual Navier–Stokes solutions. A counterexample to the former does not refute smoothness of the latter.
- **PDE-E3, scaling.** Given a smooth solution with viscosity nu and forcing f, derive the rescaled velocity, pressure, forcing and space/time domain under x→lambda*x,t→lambda^2*t. Check every transformed term and which norms are invariant. Do not infer blowup from dimensional balance.

Keep complete solutions outside generator-visible mounts. Expert review must define exact statements, scoring obligations and hard failure conditions before these become test-set items. Use unseen lemma families, not superficial numerical substitutions, for a held-out set.

## Navier–Stokes case-study boundaries

Use the original [Clay problem statement](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf) as the statement authority. The alternatives differ in domain, quantifiers, forcing and energy requirements:

| Contract | Domain | Required boundary |
|---|---|---|
| NS-C | R3, nu>0 | Smooth divergence-free rapidly decaying initial data; forcing smooth with all specified space/time decay estimates on t≥0; no global smooth solution satisfying bounded energy as in the original statement |
| NS-D | Unit periodic torus, nu>0 | Smooth periodic divergence-free initial data; forcing periodic and satisfying the specified temporal decay for every derivative; no global smooth periodic solution |

A target-hinted reproduction may specialize to zero initial velocity and compactly supported smooth forcing, as described in the supplied paper. Record that hint as an intervention. The reference and its Lean implementation are evaluator-only. Check forcing regularity through the alleged singular time; placing the singularity in the forcing does not meet this target. Do not conflate C/D with unforced A/B. Do not describe a numerical growth curve as a finite-time singularity proof.

As checked on 2026-09-16, [the formalization repository](https://github.com/openai/NavierStokesAndEuler) describes forced Navier–Stokes results and provides Lean build instructions. [Clay's announcement](https://www.claymath.org/news/navier-stokes-announcement/) describes an evaluation process. This project has not rebuilt or independently validated those proofs. The case is therefore framed as frontier-level reproduction/search with explicit contamination limits, not an undisclosed open-problem benchmark.

## Candidate and verdict records

The final submission must identify the exact task/version, candidate hash, source checkpoint/event, theorem statement, assumptions, dependency artifacts, known gaps and authorized hints. Record generator self-assessment separately from terminal verdict. Terminal evaluators are blind to arm and prior evaluator verdicts; conflicts receive evidence-based arbitration. Their costs are separately tracked with the same quota in all arms and no feedback into the scored run.

A formal pass requires exact theorem-intent correspondence, pinned Lean/Mathlib dependencies, complete build log, explicit axiom audit including sorry/admit and no circular assumptions. A natural-language pass requires independent mathematical review of all proof obligations; partial progress stays partial. An isolated accepted lemma is not an accepted full theorem. Result retractions are new provenance events and invalidate dependent claims for future use.

The current exact evaluator accepts JSON coefficients or integer witnesses only. Unsupported tasks return UNVERIFIED; prose claiming a proof does not pass. This is a small trusted-arithmetic implementation with tests, not a verified proof kernel. Future arbitrary code/Lean execution requires a sandbox and resource limits before it can accept untrusted generated programs.
