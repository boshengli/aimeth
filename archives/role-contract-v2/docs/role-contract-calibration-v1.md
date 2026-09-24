# Four-role and recorded-context calibration · v1

2026-09-23. Exploratory development protocol, frozen before new generation. Follows M2.2 without replacing its source, scores, failed cases or reports. The user authorized continued institutional testing. No services, scheduler reservations or routing are changed.

## Question and units

Does a final explicit output reminder reduce role-envelope failures across all four roles and both empty and previously generated contexts? This is prompt-contract calibration, not a new H/F organization experiment, not independent multi-round interactions, and not a mathematical efficacy result. A one-step invocation is the observation; duplicated prompts, shared task instances and reused context fixtures make generalization beyond these development cells unsupported. No p-values, model ranking or confirmatory claim is planned.

M2.2 post-hoc inspection found both standalone certificates missing the outer envelope and outputs copying the input context. These observations motivate the new treatment; they are not held-out evidence. Alternate explanations include serving behavior, sampling variability, small output ceilings and general task difficulty. A null or reversed format difference remains a valid outcome.

## Frozen design

Two served IDs: glm-5.3-flash and deepseek-v4-flash-0731. The catalog also lists deepseek-v4-flash-vision-exp; it is not included. Each model gets one minimal availability probe, max_tokens=32, temperature=0, no additional format/thinking options. A complete nonempty response with finish_reason=stop admits that model. This is an operational gate, not a mathematical or JSON-correctness gate. A failed probe skips its 64 planned calibration calls, preserving them as unstarted. No retry or alias fallback.

128 planned calibration cells: two models × two public tasks (prime-counterexample, ns-scaling-algebra-v1) × four roles (E0/E1/C/S) × two contexts (empty/recorded) × two prompt contracts (baseline/output-card) × two repetitions. Conditions form 64 paired blocks with common realized sampling seed. Hash-based block and within-pair ordering is fixed in source. Requests are serial (concurrency 1); each is independently initialized and never receives another calibration response.

The baseline is the M2.2 role system prompt, unchanged task statement and recorded-context message. The treatment appends the exact English OUTPUT_CARD in aimeth_pilot/role_contract.py. It explains nesting and prohibited extra keys but provides no certificate values. This changes instruction placement and input length together; it does not isolate a single linguistic mechanism or equate input-token cost. Both use max_tokens=1024, temperature=.6, top_p=1, response_format=json_object and chat_template_kwargs.enable_thinking=false. Server adherence is not independently attested.

The 16 fixtures in examples/role-contract-contexts-v1.json are selected before generation from the published M2.2 event file: for each task and role, take the lexicographically first (run_id, agent_id) GLM request at round 0 (empty) or round 2 (recorded). No selection uses a verdict, certificate correctness or eventual success. Preserve the complete original context, including incorrect candidates and invalid-format markers. Each fixture records its source event/request hash. These are disclosed previous model outputs, not reference answers or authorized new mathematical hints. They are not newly sent or consumed messages. No evaluator solution is given to generators.

## Evaluation and readiness

Keep the existing strict envelope parser unchanged: exactly candidate, justification, objections, used_messages; bounded strings/objects, no duplicate keys, nonfinite values or invented references. Reference checks use the exact incoming IDs in the frozen context. Do not repair outputs or search for a certificate inside malformed text. Complete format-valid output is the primary outcome over all planned cells. Report malformed, truncated/technical, unstarted and valid counts separately by model/contract/role/context. Exact mathematical certificate acceptance is secondary and evaluated only after extraction, using the unchanged task evaluator. NS scaling algebra is not a PDE proof.

Paired baseline/treatment outcomes remain linked. Report descriptive percentage-point differences on the executed paired cells, with their denominator and unstarted cells separate. Show all role/context/task strata so improvement cannot be asserted from pooled counts alone. Do not count E0 and E1 or repeated common contexts as new independent tasks.

The output-card condition must achieve 32/32 complete valid envelopes for a model to be ready for a subsequent bounded multi-round contract check. This deliberately strict operational gate does not certify a population success rate or high reliability; independent multi-round confirmation is still needed. Failure causes no extra adaptive model calls in this experiment. Mathematical correctness does not drive this gate.

## Budget, stopping and provenance

At most 130 calls including two probes; reserved output ceiling 131,136 tokens; request size <=16,384 serialized UTF-8 bytes; aggregate reserved input bytes <=2,129,920. Stop new admissions at 400,000 observed total tokens; an in-flight request can overshoot. This is not tokenizer-derived input admission, GPU-hour attribution or a hard currency budget. No unknown reservation is refunded. Unknown usage is counted explicitly.

One CPU-only Slurm client, 2 CPUs / 2G / 35-minute job limit, 30-minute coordinator deadline, 120-second absolute request limit; no new GPU allocation. Any dispatched transport error opens that model's circuit for remaining cells; length-truncated responses are retained as technical failures without transport retries. All unstarted cells and reasons remain in the 130-unit schedule. Model availability is observed at this time only; GPU01 inference location remains user-reported and actual request-to-worker/weight identities unattested.

Freeze source/fixtures/protocol and push before submission. Each invocation uses a separate transactional journal and atomic reservation ledger. Journal receipts commit before usage settlement; restart reconciles committed receipts and never redispatches a reservation. Copy closed records to shared storage. Recovery depends on retained local journals; no multi-host failover claim. Archive submitted code, full realized requests/responses/schedules, private originals, public endpoint-redacted derivatives, exact verdicts and failures. Produce a new M2.3 HTML, hash manifest, replay validator and desktop/narrow/interaction QA.
