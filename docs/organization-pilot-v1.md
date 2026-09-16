# M2.1 · Organization and mathematical pilot design v1

2026-09-16 · Exploratory implementation specification. The user authorized starting design and testing, not a claim that any architecture works. M2.1 is the first bounded M2 delivery; subsequent architecture arms, live pilot and confirmatory freeze remain separate milestones.

## Question, decisions and evidence

在相同模型、题面和预分配资源规则下，信息在群体内的分布是否改变可验收数学输出？10K 或更大是否有必要是 H4 的待检验假设，不是设计前提。组织干预、数学真伪和系统吞吐必须分开报告。

Independent unit: one isolated population × task × repetition. An agent, message, theorem fragment or retry is not an independent replicate. This release freezes executable development fixtures; it does not freeze a confirmatory experiment or select a winning architecture.

## What transfers from 0013-Workflow

| Local source inspected | Transfer | Boundary / correction |
|---|---|---|
| SLCW Universal Project Kit / discovery skill | Stable core + project adapter; minority candidates retained; negative validation is evidence | Biological candidates become explicit mathematical claims and obligations |
| DiscoveryTissue ARCHITECTURE | Exploration/validation lanes; typed feedback; dependency-local rerun; three distinct synthesis/skeptic/calibration functions | Consensus cannot discharge a proof obligation; technical error does not refute a theorem |
| Core Step 6 patterning.py | Allocate effort to uncovered hypotheses/obligations | Source routed to another model too; hold model fixed in the first AIMeth ablation |
| Core Step 6 messaging.py | Bounded, typed long-range routes | Its inbox digest transmits labels, not candidate contents. AIMeth baseline transmits bounded candidate excerpts with event provenance |
| Step 6 comparison report | Preserve all arms, costs, failures and controls | fixed used 0 LLM calls, other arms used 8–10 and different models; source-reported recall 0.90 is not evidence for a pure topology advantage or math transfer |
| H20 handoff skill + visible transcript | N logical states → bounded client queue → persistent inference server | 384 concurrency and TP4/DP2 are unverified starting suggestions; completed-ID resume is replaced by the existing transactional journal |

The source files remain read-only. Public repository contains derivative design and file hashes, not private 0013 data, prompts, raw API logs or full source copies. The source report was inspected, not independently reproduced.

## First executable family

| Arm | Population / schedule | Directed communication | Interpretation |
|---|---|---|---|
| S | 1 agent, N×R serial calls | none | Serial depth, same call-slot/output ceiling; latency not matched |
| I | N agents, R synchronous rounds | none | Independent trajectories with own checkpoints |
| L | N agents partitioned into equal groups g | Within each group, successor and predecessor, out/in degree 2 | Local exchange |
| X | Same agents/groups/roles | Local successor plus same-position agent in next group, out/in degree 2 | Replaces half of L's edges with cross-group routes |

N≥2g; g≥3; N divisible by g. Default development N=32,g=8,R=3. Seed deterministically permutes group membership using SHA-256 ordering; realized memberships and every round's edges are stored. L has isolated groups; X is strongly connected because local successor and group successor generate every position. These are particular sparse graphs, not all possible local/global architectures. The final source round has no messages.

L/X match node count, directed degrees, edge count, permitted messages, per-message character cap, model, role, prompt and schedule. They do NOT guarantee equal realized input tokens. Each message is an excerpt of the generated response, not another model call; its repeated input cost still counts. I/X tests an organization package with different communication costs, not a pure topology effect. Call-slot/output ceilings are engineering matching, not equal total compute. Strict tokenizer-counted total token and GPU-time admission remain launch gates.

## State, access and prompt contract

All baseline agents use the same solver role. Frozen system and task messages precede a short per-agent context suffix. No role-specific model or hidden tool advantage.

`pending → leased → response receipt → checkpoint + outbox → next-round inbox`; expiry creates a separately charged attempt; stale leases cannot promote results. Existing runtime records sent/bound/consumed causal chains. Round r reads only its own r−1 checkpoint and authorized messages from r−1; a single terminal failure stops the round barrier and remains a technical failure. No online topology adaptation occurs in baseline v1.

| Actor | Reads | Writes | Cannot do |
|---|---|---|---|
| Solver | frozen task; own prior checkpoint; authorized inbox | candidate text, assumptions, gaps | read other checkpoints or evaluation keys |
| Deterministic controller | graph, step/event identity, resource ledger | queue, routes, retries, selection receipt | declare a mathematical result correct |
| Candidate selector v1 | final checkpoint identities | exactly one selected candidate/event | inspect verification verdicts or cherry-pick successful candidates |
| Terminal evaluator | selected output, frozen task and evaluator package | structured scoped verdict | feed answers back to the current population |
| Observer/critic/patterning | later-arm permission specification | proposed diagnostics/interventions | silently change baseline protocol |

Solver output remains UNVERIFIED. Checkpoint is the prior response, not a full conversational memory; full receipts stay in the journal. No shared global blackboard exists in S/I/L/X. Excerpts may omit important qualifications, a measurable failure mode to inspect later.

Selection v1 is a reproducible uniform-index lottery over final agent IDs using a selection seed independent of content, with rejection sampling to avoid modulo bias. It has zero model cost and K=1 in all arms. Thus it measures **the quality of a representative final agent**, not best-of-N discovery. S has one terminal agent. This deliberately simple diagnostic selector may favor dissemination over isolated search; conclusions must state that estimand. A paid pooled selector, blind to arm and using a fixed candidate pool/context budget, requires its own later contrast before claiming best available mathematical discovery. It must not select using terminal evaluator answers.

## Mathematical testing ladder

1. Public development controls: exact polynomial identity certificates (two tasks), polynomial antiderivative certificates (two tasks), an integer Bezout certificate and an explicit counterexample to a universal polynomial primality claim. Small exact-arithmetic checkers compare coefficients/equalities; they never execute submitted code. Valid/invalid/malformed objects are tested. Public fixtures are contaminated calibration material, never held-out accuracy.
2. PDE bridge tasks: derive the smooth periodic energy identity with forcing; diagnose why an L2 energy bound alone does not prove L-infinity control; verify viscosity/space/time scaling and missing assumptions. These require independently reviewed task contracts and proof rubrics. They are specified, not automated or expert approved here.
3. NS-C/NS-D case studies: reproduce or independently search the forced breakdown alternatives in the original Clay statement, with exact smoothness/decay/periodicity quantifiers. Keep whole-space and torus separate; target hints versus source-blind material are separate conditions. Reference PDF and formal proof repository stay evaluator-only. Do not call this an undisclosed unsolved benchmark or equate it to unforced regularity. Source announcements and formalization availability are not our own proof validation.

Retain Navier–Stokes as the initial frontier-level case; no second frontier problem is silently substituted. Source/date/formal statement hashes, proof obligations, allowed information and exact version need specialist sign-off before live use. The six exact controls test the measurement machinery; their difficulty says nothing about 10K usefulness. A real effect pilot must use calibrated multi-step tasks with headroom, not only these controls.

Terminal outcomes: VERIFIED_WITHIN_SCOPE, INVALID_CERTIFICATE, MALFORMED, UNVERIFIED (unsupported free text), TECHNICAL_FAILURE, BUDGET_EXHAUSTED. Certificate success proves only the fixed encoded algebraic assertion; no general proof checker or Lean build is implemented. For frontier natural-language proofs, require independent mathematical reviewers, dependency checks and, when used, exact Lean theorem/axiom/build verification. Do not turn confidence or consensus into acceptance.

## Next architecture sequence, all still proposed

| Stage | New arm | Clean comparison and mechanism |
|---|---|---|
| M2.2 | H: local explore/critic/synthesizer hierarchy | H vs role-matched flat graph; same model and total budget; detect error propagation |
| M2.3 | A: adaptive allocation to unfinished proof obligations | A vs schedule-yoked nonadaptive allocation; reserve fixed maximum N and total calls |
| M2.4 | P: patterning / minority branches | P vs random reassignment with same spawn count and prompts; test coverage without changing models |
| M2.5 | V: typed long-range communication | V vs equal-degree random cross-group delivery and shuffled-content control; test useful evidence transfer |

A claim record needs statement/assumptions/domain/dependencies/artifact hashes/author status/evaluator status. Proposed → internally criticized → selected → independently reviewed; refutation retracts dependent claims via new events, without erasing history. Content priority and spawning are interventions whose own inference costs must be charged. A source's three-Chief titles do not require three extra unbudgeted models.

## Pilot, scale and analysis

Exploratory first: development task family × S/I/L/X × 3 independent population repeats, randomized arm order within task/repetition blocks. Three repeats are only a variance/cost diagnostic. Do not run significance tests on model-free traces or checker fixtures. With real pilot data, estimate family-level heterogeneity, missingness and technical-failure rates; use a predeclared meaningful difference and power simulation to set held-out family and run counts.

Separate scales N=32,128,1000,10000 (then larger only after capacity evidence) from fixed calibrated client concurrency C. Study both (a) fixed total budget redistributed across N, requiring fewer per-agent calls, and (b) fixed per-agent budget, reporting that total compute grows. S has matched N×R slots but one active agent. Current planner exposes the growing-budget regime only and labels it explicitly; it does not purport to implement (a).

For real comparisons report selected-output success by planned-run denominator, matched-arm differences and family/block-aware uncertainty. Keep unsolved, malformed, technical failure and budget stops visible. Analyze time-to-verified result with censoring and competing technical failure as specified before the confirmatory run. Do not treat small P values as proof. Hold out entire task/lemma families, keep pilot and held-out data separate, freeze model/prompts/selector/graph/budget/stops, and preserve negative runs. No confirmatory sample size or positive effect is asserted now.

## Submission design and launch gates

One allocation per active population/batch; one persistent inference service with bounded clients; 10K logical states are queued on local durable storage. Do not use one GPU job per logical agent. Slurm arrays may later index independent population runs subject to site limits, not individual mathematical agents. No database shared on NFS; future multi-host workers require a journal service or transactional database redesign.

Planner records N, C, R, max attempts, output-token ceiling including retries, optional maximum prompt tokens per attempt, and resulting conservative total-token ceiling. Missing prompt bound yields null total-token bound, never zero. These are arithmetic bounds conditional on configured limits, not measured GPU-hours or enforced global reservations. Model context/tokenizer and prompt growth must be measured first.

Before live launch: verified SSH/endpoint and scheduler/GPUs; model/weights/tokenizer/chat-template/container hashes; known spending ceiling; atomic reserve-before-dispatch and reconciliation including retries/unknown usage; whole-call deadlines and supervised worker recovery; generator/evaluator mount isolation; calibrated concurrency and cache conditions; task/evaluator review. No live sbatch command is generated with guessed resource flags. The shipped local dry-run is executable and cannot issue model requests.

## Reproduction / acceptance

See README M2.1 commands. `python3 -m aimeth_design` provides compile, plan, dry-run, select and evaluate. Baseline manifests run on the existing journal via the frozen candidate-broadcast policy. Dry runs label every output synthetic and test routing/lineage, not solver quality. The runtime package is unchanged so M1.1 snapshots remain valid. M2.1 acceptance is executable organization definitions, exact-control evaluator tests, 10K manifest planning, checked traces, source audit and versioned HTML; mathematical effect measurement is a subsequent milestone.
