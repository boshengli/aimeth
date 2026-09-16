# M2.1d · Service identity and output-contract calibration

Date: 2026-09-16. Exploratory follow-up to the institutional population pilot; the user authorized continuing this work. No prior run or report is changed.

## Questions and interpretation

1. Which existing node/model configurations can be directly inspected, and which service labels can be linked to independently checked weights? Record permission-denied observations instead of inferring the gateway route. Stored model files, active processes, scheduler allocations and gateway labels are distinct evidence.
2. Can a task-independent output-contract reminder reduce malformed certificates? Does increasing the output ceiling from 512 to 2048 change truncation or exact-certificate acceptance? Treat these as diagnostic factors, not interventions on population organization.
3. Introduce a bounded Navier–Stokes scaling-algebra control. An accepted exponent certificate verifies the encoded scaling identities only. It is not an independently reviewed PDE proof, regularity result or frontier discovery.

## Frozen exploratory calibration

- Two institutional served IDs: `deepseek-v4-flash-0731` and `glm-5.3-flash`. Weight identity and gateway routing are explicitly provisional until actually attested.
- Three public development tasks: `integral-rational`, `prime-counterexample`, `ns-scaling-algebra-v1`.
- Factors: original solver system prompt vs appended task-independent certificate-only reminder; output ceiling 512 vs 2048; two independently initialized repetitions. Total 48 single-step cases. Common sampling seeds within model/task/repetition blocks, recorded deterministic randomized condition order.
- Same temperature 0.6, top_p=1, `chat_template_kwargs.enable_thinking=false`, `response_format.type=json_object`; concurrency 1, no automatic retry. The reminder supplies no solution values, hints, evaluator results or reference examples. It does clarify index order and JSON field compliance for all tasks.
- At most 48 request reservations and 61440 reserved output tokens; 15-minute wall deadline, at most 120 seconds per supervised HTTP request, request <=16384 bytes. Slurm CPU client limit 20 minutes. No full input-token or attributable GPU-time budget is claimed.
- Every request is a fresh one-agent, one-step journal with no cross-case memory. This is an output-contract experiment, not a multi-agent effect comparison. Server caching and stochastic nondeterminism may still exist. Preserve actual prompts/responses and all failures.
- Primary diagnostic counts: transport failure, generation truncation, malformed certificate, invalid mathematical certificate, exact certificate passed. Score strict whole-object JSON; no substring extraction, schema relaxation or post-hoc candidate selection. Planned denominator remains 48 even if execution stops.
- Two repeats per cell are descriptive only. Keep pilot/test split, all factor levels, costs, negative findings and route uncertainty visible. Do not choose a topology winner or claim model-family superiority.

## Mathematical scope

The equation and three-dimensional whole-space domain follow [Fefferman's official Clay statement, equations (1)–(2)](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf), accessed 2026-09-16. The scaling certificate is a project-authored algebraic development task, not a task endorsed by Clay. Its solution constraints are derived by chain rule and change of variables; the source is not cited as supplying the generated benchmark or evaluator.

Assume a smooth forced incompressible solution on R3 and viscosity nu>0. For lambda>0 set u_lambda(x,t)=lambda^a u(lambda*x,lambda^b*t), p_lambda similarly with exponent c, and f_lambda with d. Find integer exponents preserving the equation for arbitrary smooth solutions with nu unchanged; record L2-squared and L3-norm scaling powers at the corresponding times, assuming those norms are finite. The rescaled time domain is defined by lambda^b*t in the original domain. No periodic-torus invariance or singularity assertion is included.

The evaluator checks equality of the five PDE-term exponents, the two norm powers and exact schema. It does not verify the generator's derivation, a general proof, initial-data/forcing decay through singular times, or a Lean theorem. All task material is public development data and unsuitable for a held-out benchmark. Full reviewed PDE/NS proof tasks remain a later gate.

## Outputs and next decision

Preserve read-only inventory receipts, hashed model metadata, exact case journals, reservations, verdicts and source commit. Produce a versioned HTML with factual identity levels, factor tables, PDE-control scope, failure accounting and next-stage readiness. Only after observing these diagnostics decide the next separately frozen calibration or organization pilot; no additional factor levels are silently added to this run.
