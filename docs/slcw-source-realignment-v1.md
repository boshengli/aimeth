# SLCW source recovery and research realignment — v1

Date: 2026-09-29. Status: source audit complete; mathematical adaptation proposed; no new population run. Baseline: `8b56634efae095945cc6ae7deb2cd3f7d7854fe1`.

## Research decision

The user clarifies that the primary object is population-level computation and governance emerging from agent organization. The two existing SLCW designs in 0013-Workflow are the starting architectures. A capable single agent is **not** an admission requirement for collective experiments. A single-agent condition may be an optional resource-matched comparator. Transport, accounting, isolation, recovery and evaluator integrity remain engineering requirements; mathematical failure is an outcome to retain.

This supersedes the *future-work priority* in `next-population-plan-v1.md` and the earlier decision to defer the source architecture behind serial capability calibration. It does not alter historical scores, failed gates, frozen protocols, or reports. Earlier S/I/L/X and N8 H/F runs are simplified pilot systems; they do not test the full SLCW architectures.

The user's 2026-09-29 GPU08 clarification also supersedes the pause in D-015: the previous group Slurm job has stopped (user-reported), and the user authorizes renewed project use. The control plane responded; the project account obtained all eight H20 devices under the existing `Res_libs` reservation. Job 230643 completed an eight-device CUDA smoke check. Direct SSH was not established during an active GPU job because this short job exited before a confirmed authenticated session; use a longer, real experiment job for that access check.

## Recovered lineage

Source identities, inspected ranges and hashes are recorded in `milestones/m2-6-slcw-realignment-v1.sources.json`. Originals remain in 0013-Workflow; they are not embedded in the public repository. The audit is source inspection, not reexecution or verification of the pepper paper's biological claims.

1. **SLCW V1 original note:** `za/01.GTPplant.md`, lines 5–10, specifies 10×10 analysis agents, four regional Observers, one Chief, COLOR, Quarantine, 30% neighbor communication and 80% global convergence. The linked sandbox ZIP has not been recovered by this audit. Later DPV4/LUNA files explicitly call themselves reconstructions; they must not be described as the original ZIP.
2. **Layered reconstruction:** DPV4's `20260810_层状Agent分析架构设计_DPV4.md`, lines 80–138, maps layer/time cells to analysis units and layer domains to Observers. Its particular domains and long-range additions are reconstruction choices, not all properties of the minimal original note.
3. **Richer specification:** `SLCW_Runtime_v0.1/spec/SLCW_Final_DiscoveryTissue/ARCHITECTURE.md`, sections 2–12, describes exploration/validation lanes, adaptive analysis tissue, Patterning Agents, Interface Agents, a Vascular Network, dynamic Observers, candidate harvesting, feedback and synthesis/skeptic/calibration Chiefs. `FINAL_DECISIONS.md` separates candidate discovery from consensus and STOP from scientific truth.
4. **Partial implementations:** GLM has real top-N requery and long-range message filtering. One global PatterningAgent does not establish per-layer TF-like agents; a software VascularRouter does not establish independent LLM vascular agents. Codex records named roles, but its inspected worker uses a common analysis role and deterministic adaptation markers. Core Step6 changes the model for patterning and its inbox digest includes message labels without candidate content. These branches are useful components, not interchangeable complete realizations.

The user's “微管束” corresponds most closely to the recovered **Vascular / 维管** terminology. A one-to-one equivalence between a biological TF, an LPTF candidate in the data, and an implemented regulating Agent has not been established. The proposed mathematical regulator role below is an explicit adaptation.

## Counting without ambiguity

The original note specifies **100 analysis agents**, not 100 populations or 100 multi-agent groups: 100 + 4 + 1 = 105 named roles. Active units and actual LLM invocations may be fewer; the GLM biological coverage configuration activates only 34 of 100 cells.

Keep separate fields for `analysis_agents`, `groups`, `agents_per_group`, `governance_agents`, `active_agents`, `client_concurrency`, and realized calls. A proposed 100 groups × 100 workers is 10,000 analysis agents **plus** governance, not an already recovered original configuration. The user's current group-count wording remains unresolved for launch; preserve both count interpretations in the scale plan until its configuration is specified. Do not silently replace 10K live inference by a manifest compilation or a mock run.

## Mathematical adaptation to implement

| Source mechanism | Proposed mathematical behavior | Evidence required before calling it implemented |
|---|---|---|
| Layer/cell specialization | Groups pursue proof obligations, alternative lemmas, counterexamples and methods | Assignment and realized role prompts; no evaluation keys in contexts |
| Observer / Chief | Track dependencies and disagreement; produce a collective candidate and unresolved obligations | Candidate-to-source lineage and explicit dissent; synthesis included in budget |
| COLOR / Quarantine | Mark claim status and isolate unsupported or corrupt messages; preserve challenges and appeal paths | Status/reason events; minority claims cannot be discarded merely for disagreement |
| Patterning / TF-like regulation | Regulate per-layer role allocation and activate neglected alternatives under a fixed total budget | Actual allocation changes and distinct task prompts; independent of model replacement |
| Interface | Check whether local lemmas have compatible assumptions at module boundaries | Exact assumptions, counterexamples, rejected joins and repair events |
| Vascular | Deliver bounded, typed long-range candidate, contradiction and tool-result content | Source/target IDs, content hashes, delivery/consumption records; labels alone are insufficient |
| Candidate harvest / feedback | Surface candidates before consensus and rerun the affected dependency subgraph | Versioned candidate DAG, feedback ancestry, localized revision history |

V1's 80% threshold concerns coordination. It never certifies a proof. V2's candidate harvesting must preserve discoveries that lack majority support. Both require an independent final checker outside the generating population. A final random agent is not an adequate primary readout of collective synthesis.

## Proposed comparisons, not a frozen confirmatory protocol

The initial engineering target is the original 100-worker V1 and a behaviorally complete V2 adaptation at a documented worker/governance allocation. This is not an instruction to launch 100 groups immediately. Scale testing then covers 1K and 10K workers without requiring a favorable scientific result at a smaller size.

- **Primary architecture comparison:** faithful V1 versus faithful V2, estimating the effect of the whole organizational package, not a single mechanism. Include an independent-population comparator with an equally budgeted, prespecified aggregation opportunity.
- **Mechanism comparisons:** within V2, switch Patterning on/off and Vascular on/off in a 2×2 design while keeping Interface/Observers/Chiefs fixed. This separates both marginal effects and their interaction. A later governance ablation must specify exactly which policy changes.
- **Resource controls:** freeze model/version, task instances, initial information, tools, decoding, total input/output token ceilings, validation/aggregation allowance, communication cap and wall time. Count governance and retries. A disabled mechanism's reserved budget must have a prespecified nonadaptive allocation, not disappear. Report realized resources and unused allocation. Equal call counts alone do not mean equal compute.
- **Readout:** prespecified collective submission at deadline/budget, exact-task verified success, accepted proof obligations with dependency validity, false-acceptance rate and duplicate-free contributions. Frontier NS exploration is reported separately from benchmark success; a lemma or scaling certificate is not the full NS result.
- **Governance stress trials:** separate clean and prespecified perturbation runs. Inject known-invalid claims, conflicting assumptions, dropped messages or worker failure; measure error spread, detection/repair delay, minority-candidate retention and safe recovery. Hidden perturbation truth belongs to the evaluator. Agreement alone is not quality.
- **Replication/statistics:** separately initialized populations on a task instance are independent units. Agents/messages are dependent observations. Randomize/block architecture by task and provider; isolate state across arms. Pilot results estimate resource needs and variance. Freeze held-out tasks, replication count, primary contrasts, analysis and stopping before confirmatory runs. Do not treat a low P value as mathematical proof or promise emergence at 10K.

## Immediate next work and acceptance

Implement a math task adapter and actual SLCW routing/regulation atop the existing event runtime; use explicit source-to-behavior acceptance checks. A deterministic fixture can validate delivery, synthesis ancestry and checkpoint replay without waiting for any individual agent to solve a task. Then freeze a bounded collective pilot with exact counts, budgets, task/evaluator versions and stopping rules, commit its source, and submit through an available authorized institutional route. GLM/DeepSeek remain preferred; GPU08 recovery is deferred under the user's instruction.

Ready to design: yes. Ready to implement: yes, with the mapping above explicitly proposed. Ready to claim a faithful live comparison: no. No new model requests or cluster jobs were made for this audit. Existing mathematical single-agent failures neither disprove population emergence nor establish it.
