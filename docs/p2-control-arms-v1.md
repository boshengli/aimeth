# P2 matched control arms · v1

Date: 2026-10-04. Status: frozen seven-arm engineering protocol for T-20261004-002. The implementation and fake/replay tests are locally verified. Phase B has been launched; its immutable execution snapshot and the later Amendment 3 task-set pairing audit are recorded in `milestones/m2-14-p2-control-arms-v1.html`.

## Question and interpretation

These arms are baselines for a later comparison with the developmental-organisation arm. They do not instantiate cell differentiation or spatial/tissue formation. A difference between arms will be an empirical property of this model, prompt, task set, evaluator, and run budget; it is not evidence that developmental organisation works. One run per task and arm is planned, so task-bootstrap intervals are exploratory and do not replace repeated independent population initialisations on each task.

## Frozen matrix

All seven arms use the same parameterised model adapter; the Phase-B run card pins provider `deepseek`, model `deepseek-flash`, enabled thinking, and low reasoning effort for ARC-AGI-2 / medium reasoning effort for callus imputation. No GLM or local-model arm is part of Amendment 2. The API key must be present as `DEEPSEEK_API_KEY` in the local process environment. The runner refuses paid dispatch when that variable is absent and never prints or stores its value. The same environment key has precedence over the legacy private config fallback, so this campaign does not use the fallback.

| Item | ARC-AGI-2 | Callus imputation |
|---|---:|---:|
| Task denominator | 40 of the official 120 evaluation tasks | All 36 frozen P2 tasks |
| Task sampling | Sort by SHA-256 of `T-20261004-002:ARC2-eval-pilot-v1:<task_id>`, select the first 40; no difficulty/result stratification | Fixed task IDs in the existing P2 benchmark |
| Model / replicate | `deepseek-flash`; seed 1000; one run per task and arm | Same; validation seed 1000 |
| Per-task ceiling | 8 logical calls; 262,144 completion/reasoning tokens across calls | Same |
| Multi-call arm cap | 32,768 output/reasoning tokens per call | Same |
| Single-long cap | One call; effective cap `262,144`, equal to the per-task token ceiling and below the current official `deepseek-flash` maximum output of 384K; the requested cap is recorded | Same |

The call and token values are ceilings. Unused tokens after early stopping are not filled with dummy output. Provider-reported prompt tokens are recorded separately and do not count toward the frozen completion/reasoning budget. If usage is unknown after a timeout, the entire requested output cap is reserved against that task's token ceiling, and the request is not repeated. A DeepSeek HTTP 429 is treated as an explicit rate-limit rejection and retried under the existing AIMD pause; other errors and unknown outcomes are retained without retry. Cost estimates are informational only and do not stop this run. They use the repository's conservative historical price estimator and are not a provider invoice.

The ARC-AGI-2 archive SHA-256, all 120 public-view hashes, and the preselected 40 task IDs/hashes are frozen in `plans/arc2-eval120-v1.json` and `plans/arc2-pilot40-v1.json`. The loader returns training input/output pairs and test inputs only. Test outputs are never put in model prompts. The callus generator receives only the public prompt fields; the answer-bearing prediction keys remain on the private evaluator filesystem. The exported callus manifest is checked against the per-task hashes and whole-manifest SHA-256 in `plans/callus-public-prompt-hashes-v1.json` before any model dispatch; the raw prompt manifest stays in ignored run storage.

## Arm algorithms

Every generated program is scored on the visible training/pseudo-task check. The final program is selected by that visible check alone. A train-perfect ARC program ends further sampling for that task. Real hidden-test grades are computed only after generation has finished.

| Arm | Algorithm and default call allocation | What it controls for |
|---|---|---|
| `independent` | Up to eight independent initial-prompt samples; choose the best visible score (earliest tie) | Parallel independent sampling and visible-check selection |
| `self_repair` | Up to eight sequential attempts; each later attempt receives only the preceding program and visible feedback; choose the best visible score (latest tie) | Within-agent sequential feedback |
| `single_long` | One request with the recorded model cap; select its output | One uninterrupted reasoning trace under the largest allowed per-call context |
| `vote` | Up to eight independent samples; ARC outputs are voted inside the private evaluator with ties resolved by best visible training score then stable source order; callus arrays are averaged there | Aggregation of parallel samples |
| `orchestrator_worker` | Default `k=4`: one plan request, four worker programs, then a budgeted assignment plus worker revision while calls remain; any final unpaired slot is a worker revision | Explicit planning and division of work |
| `debate` | Default `m=3`: three initial proposals followed by up to five turns that expose only programs and visible checks to the debaters | Peer critique and iterative revision |
| `evolution` | Identity seed for ARC, one planning call, then up to seven model mutation/crossover proposals; deterministic selection keeps the highest visible-check population (`population_size=8`) | Non-spatial search with selection and variation; no cell types or differentiation |

The evolutionary baseline follows the non-spatial selection/mutation search in source branch `codex/p2-arc` at `8b9bab669842fdb99dee081e2135968d03501c5d`; this implementation adds a deterministic alternating crossover prompt as specified in T-20261004-002. Prompts are English. Stable prompt-template hashes are in `plans/p2-control-prompt-hashes-v1.json`, and every realized request records the SHA-256 of its canonical message JSON and the template hash when applicable.

## Hidden-output boundary and runtime

The controller and model calls run on the user's Mac. The DeepSeek key stays in that local process environment. Programs and aggregation requests travel over key-based SSH to a new, isolated evaluation queue on GPU08. The queue daemon is a CPU-only job pinned to GPU08 with 8 CPUs and 32 GB RAM; it requests no GPU. DeepSeek performs model inference remotely, and the sandbox evaluator executes candidate programs on the node. Existing queue/job `240170` and the low-power holder are not changed. No `tcu165` job is used.

The evaluation service runs each candidate in the existing no-network sandbox. Private ARC test predictions and callus predictions remain in the evaluator's private directory. The controller can see only training/pseudo-task scores. The vote/mean operation is performed by the evaluator from private predictions and returns contributor IDs, agreement counts, or visible-score summaries; it does not return test grids or answer-bearing arrays to the controller. The fake evaluator tests cover tie rules, task identity checks, path traversal rejection, and non-leakage of aggregate predictions.

Each task gets a durable `task_started` record before model dispatch and an fsynced result record after settlement. A restarted launcher skips completed tasks. A previously started task with no settled record is finalized as an explicit unknown result, with unknown call/token usage, retained in the denominator, and never resent. After the controller is stopped, `tools/finalize_p2_incomplete.py` can account for any remaining never-started items as `not_started`; it makes no model calls. `tools/postprocess_p2_controls_phase_b.sh` is the later grade/audit/analysis path and never invokes the model runner. Provider receipts remain under ignored `runs/p2-controls-v1/receipts/`; they are not committed. The run auditor checks the complete 40/36 denominator, one replicate, model identity, call/token ceilings, per-call cap, and start/result pairing.

## Grading and analysis

After all generation processes stop, `tools/rt_grade.py` computes exact ARC task success under the existing two-attempt grading rule and callus pattern/cell correlations from the private evaluator keys. The grader does not send answers back to any model. `tools/analyze_p2_controls.py` reports the fixed denominator and ungraded count for every arm. ARC success is binary. For callus, a task without a valid final grade contributes zero to the operational mean and remains in the denominator; it is also reported as ungraded. Paired differences use independent as the reference. Bootstrap resampling is over paired task instances (10,000 draws, seed 1000); it is exploratory because there is only one initialised population per task/arm in this order.

The API-backed Phase B is explicitly approved by Amendment 2, but no call is sent before the code/docs commit, ARC selection manifest, callus prompt hashes, and evaluator readiness checks are complete. The detached launcher runs arms in the fixed order listed above, each with ARC followed by callus, and writes checkpoints/receipts. It uses the same four-budget contract for every arm; it never schedules a second run for a started task.

## Amendment 3 pairing audit (after launch)

Amendment 3 identifies the developmental arm's frozen task set at `/data/libs/aimeth/rt/tasks/arc2-pilot40.json`. The Phase-B controller had already frozen and started the 40 tasks in `plans/arc2-pilot40-v1.json`. A read-only comparison found only 9 shared task IDs out of 40. Both lists are preserved in `plans/arc2-pilot40-developmental-pairing-reference-v1.json`; the running records are not rewritten and no started request is resent. This run remains a budget-matched comparison among the seven control arms on its own task set, but it is **not task-paired to the developmental arm**. Do not report the current developmental-versus-control result as a paired comparison or combine only the 9 overlapping tasks as if they were a prespecified sample. Any new paired run would need its own frozen run card and authorization.

## Sources and unresolved limits

- D-038 item 5 and D-039 item 1: comparison purpose and non-spatial evolutionary search requirement.
- D-042: ARC-AGI-2 is the evaluation task family; call and total output-token ceilings are both matched; include a single-long control.
- T-20261004-002 Amendment 2: DeepSeek may be used throughout all arms; Phase B is approved; one replicate and specified task/budget matrix.
- [DeepSeek official model/pricing documentation](https://api-docs.deepseek.com/quick_start/pricing/) currently lists a 384K maximum output for `deepseek-flash`; the frozen 262,144 request ceiling is the lower per-task budget. [Official error codes](https://api-docs.deepseek.com/quick_start/error_codes/) classify HTTP 429 as rate limit reached; [rate-limit documentation](https://api-docs.deepseek.com/quick_start/rate_limit/) explains concurrency constraints.

No results are claimed here. A completed software test is not a mathematical proof or a capability result. A one-replicate pilot cannot establish a general organisation advantage or a developmental mechanism.
