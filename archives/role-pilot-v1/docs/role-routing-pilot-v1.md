# Role-routing runtime and bounded institutional pilot · v1

2026-09-20. Exploratory development protocol, frozen before new generation calls. Supersedes the unimplemented status of the H/F proposal only after implementation validation; the archived proposal and prior results remain unchanged. This is not a confirmatory preregistration or a task set held out from development.

## Site and question

The user states that GLM-5.3-flash and DeepSeek-V4-flash now run on GPU01 and supplies the existing institutional gateway and exact catalog IDs. Use `glm-5.3-flash` and `deepseek-v4-flash-0731`; do not test the vision variant. Treat GPU01 deployment as user-reported, distinct from independently attested request-to-worker routing or weight identity. On 2026-09-20 the scheduler reports all eight GPU08 GPUs allocated; use only a small CPU client in the existing account reservation, without allocating or restarting GPU services. GPU01's scheduler reservation belongs to another account; do not submit jobs into it.

Narrow question: with fixed models, roles, per-node degrees, call slots, rounds, message ceilings and candidate selection, how do the specified H and F routes behave on public exact controls? Primary outcome is selected-synthesizer strict certificate acceptance over every planned population, with technical failures and unstarted populations visible. This pilot measures implementation feasibility and descriptive outcomes, not general architectural superiority.

## A. Separate task/representation diagnostic

16 planned independent one-step requests: 2 models × 2 tasks (integral-rational and ns-scaling-algebra-v1) × 2 representations × 2 repetitions. Conditions are deterministically randomized, with common sampling/selection seeds inside model/task/repetition blocks.

- `minimal-certificate`: the unchanged public task, concise common mathematical system instruction, no recorded-context user message, standalone exact certificate.
- `role-envelope`: the same task with the frozen explorer role and envelope contract used below, plus the recorded context. Extract only `candidate`; never search for embedded JSON or repair fields.

Both use max_tokens=1024, temperature=0.6, top_p=1, response_format=json_object and chat_template_kwargs.enable_thinking=false. Server adherence to thinking/sampling options is not independently attested. This comparison intentionally changes both context and output representation; it does not isolate a single prompt component. Report mathematical and format outcomes separately. It is selected after previous antiderivative failures, so no pooled comparison to the September 16 pilot.

Before phase B, a model must have at least 3/4 phase-A envelope cases with a complete response and valid bounded envelope. Mathematical correctness does not determine admission. A model with fewer valid envelopes has all eight planned phase-B populations marked unstarted, not deleted. This gate is an engineering choice based on a tiny calibration sample, not evidence of reliability. HTTP 401/403/404/429 stops subsequent requests to that model for this experiment; no silent alias fallback or retries.

## B. H/F pilot

16 planned populations: 2 models × 2 tasks (prime-counterexample and ns-scaling-algebra-v1) × 2 independently initialized repetitions × H/F. N=8, R=4, two isolated groups of four. The unit is a population on a task instance, not an agent/message. Common group/role assignments, sampling and terminal-selector seeds within each model/task/repetition pair; randomized pair order and H/F order; separate journals and no cross-population memory.

H edges: E0→C, E1→C, C→S, S→E0, S→E1. F edges: E0→E1, E1→C, C→S, S→E0, S→C. Each node's degree is matched. Both graphs have diameter three; groups are not globally connected. Each population has 32 call slots and 30 planned messages. F is this specific routing control, not every flat organization.

The exact role prompts and common output contract are compiled into per-agent request messages in `aimeth_design/role_routing.py`; roles are identical between arms. E0/E1 explore; C checks concrete errors and missing assumptions; S synthesizes while retaining unresolved objections. In round zero all roles create their own candidate because no peer material exists.

Strict output: exactly `candidate` (object, <=512 canonical characters), `justification` (string <=512), `objections` (<=3 strings of <=160 characters), `used_messages` (<=2 unique exact IDs from the current incoming list). Duplicate keys, prose, additional fields, nonfinite values and invented references fail the envelope. Combined transmitted object <=2048 canonical characters; raw output <=8192 UTF-8 bytes. Valid envelopes are sent in full; no silent truncation or selective critique compression. Format-invalid but otherwise complete responses retain raw receipts, save a null candidate and broadcast a standardized invalid-envelope marker. They can be revised in later rounds. No mathematical feedback enters generators. Transport, empty or length-truncated responses stop that population at its incomplete round; all receipts remain recorded.

One final-round S is selected from the frozen two-agent pool before evaluation by the same content-blind lottery in both arms. It estimates a representative synthesizer, not best-of-N. A malformed selected envelope fails even when another candidate is correct. This selector and envelope differ from earlier S/I/L/X, so do not pool arms. `used_messages` is a model-reported reference constrained to delivered messages; it does not prove that a criticism was causally used or is mathematically sound.

## Budget and recovery

Phase A: <=16 calls, 16,384 reserved output tokens, <=16×16,384 serialized input-request bytes. Phase B: <=512 calls, 524,288 reserved output tokens, <=512×16,384 request bytes. Each request <=16,384 UTF-8 bytes; phase A concurrency 1, phase B concurrency 2. No inference retries. Combined <=528 calls and 540,672 reserved output tokens. All dispatched/unknown reservations remain charged. Forty-minute coordinator deadline; each supervised request <=120 seconds; Slurm CPU job <=45 minutes, 2 CPUs / 2 GB. No new GPU resource allocation.

The input-byte limit includes the serialized client request, not the server's rendered chat template. It is a hard byte admission limit, **not** a verified tokenizer-derived input-token cap. Stop new phase-A/B admissions when reported total tokens reach 32,768 / 786,432 respectively; already in-flight responses can overshoot that observed-usage stop. No total GPU-hour guarantee or currency estimate is claimed. Accurate pre-dispatch token accounting awaits the actual tokenizer/template identity or a trusted server count API.

Commit the full response into the transactional journal before settling its usage in the reservation ledger. On restart, reconcile committed receipts into the ledger; never redispatch a reserved attempt. Resume existing frozen manifests and completed checkpoints. An unanswered attempt expires its lease and remains a failure with unknown usage; no hidden retry. Copy closed journals to shared storage after each population. Coordinator restart from preserved node-local journals is supported; automatic recovery after loss of those journals or multi-host leader failover is not.

## Verification, isolation and reporting

Before live submission, check per-agent prompt binding, all allowed/forbidden routes, degree matching, reference validation, negative envelope fixtures, lottery constraints, round-boundary resume, receipt-before-ledger crash recovery and hard byte/call/output admission. Preserve all actual requests, responses, schedules, failures and source identities. Current generation is HTTP-only; evaluators and reference witnesses are never included in model messages, retrieval or tools. Evaluation runs after selection on the coordinator, not in a generator tool. Strong OS-level evaluator process isolation remains a later gate.

Exact controls are public development data. NS scaling checks the previously documented exponent equations, not a PDE proof. No p-values or equivalence claim from two repeats/task. Produce a versioned HTML with all 16+16 planned units, the gate decisions, byte/token limits, actual calls/messages, failure reasons, source snapshots, model identity uncertainty and next-stage readiness. Preserve the earlier reports/manifests verbatim.
