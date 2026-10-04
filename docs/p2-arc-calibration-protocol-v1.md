# P2 ARC difficulty calibration and evolutionary control

Status: exploratory calibration protocol. Source branch: `codex/p2-arc` from `claude/aimeth-dev`.

## Input and information boundary

- ARC-AGI-1 evaluation data are loaded from the locally archived release with SHA-256 `a87291143a4d5206cb5264eeb280a1b9c367e3523a992f4eff5702265471dbac`. The task work order identifies upstream ARC-AGI-1 commit `399030444e0a`. The archive also contains ARC-AGI-2, which this calibration does not use.
- The prompt contains training input/output pairs and test inputs. Test outputs stay in the local grader and are never sent to a model or mutation operator.
- Each model is asked for one Python `transform(grid)` program per independent request. Four independent requests are made per task and model. A candidate must produce one exact output for every test input; the grader separately supports this project's maximum of two attempts per test output for future arms.
- The two-attempt limit follows the [ARC Prize 2024 technical report](https://arcprize.org/media/arc-prize-2024-technical-report.pdf) and this work order. The [original ARC-AGI-1 repository](https://github.com/fchollet/ARC-AGI) describes three trials, so the two-attempt rule is an explicit project/competition convention, not an invariant of every ARC release. The four programs here are *calibration samples*, not four guesses in one official submission.
- Any HTTP error, transport uncertainty, missing program, rejected program, invalid grid, timeout, or wrong answer is counted as unsuccessful. An ambiguous dispatched request is never automatically duplicated.

## Frozen API condition

After a single DeepSeek v1 request used all 8,192 output tokens on reasoning and produced no final program, v2 fixed thinking enabled, `reasoning_effort=low`, `max_tokens=12,288`, and bounded client concurrency 16 for both providers. DeepSeek uses `deepseek-flash` at the official Chat Completions endpoint; Zhipu uses `glm-5.3-flash` at the Z.AI Chat Completions endpoint. Provider Batch is not used: the previously observed GLM Flash Batch upload was rejected, and current official DeepSeek documentation did not establish a supported Batch API for this model. The 8,192-token v1 request remains a separate failed receipt and is excluded from v2's four samples per task.

Request and response bodies, HTTP status, finish reason, usage, latency, provider model identifier and unknown outcomes are saved to append-only private JSONL under `/Volumes/Expand/0023-AIMeth_scratch/p2-arc/`. No credential or Authorization header is saved. Public results contain aggregates and hashes only. Provider spending is bounded independently to CNY 300 using current listed peak uncached rates and an intentionally conservative internal 10 CNY/USD budget multiplier; usage-derived values are estimates, not audited bills. The full 1,600-request v2 worst-case envelope is about CNY 256 for DeepSeek and CNY 108 for Zhipu. No retries are dispatched for uncertain calls.

## Program grading

The evaluator checks the same `transform` program on all training and hidden test inputs. Exact grid equality is required, including shape, integer type and colors 0–9. The candidate child receives input grids only and runs under a two-second wall limit. On macOS, the process sandbox denies writes and network access; a restricted Python namespace and syntax allowlist remove file I/O and dynamic execution. This is a practical research sandbox, not a formal guarantee against all malicious code. A Linux run fails closed without an OS sandbox backend.

An early incremental scorer used a syntax policy that incorrectly rejected ordinary single-underscore local names and some safe NumPy/grid methods. Its score ledger is preserved as `scores-preliminary-validator-v1.jsonl` outside the repository. The evaluator was corrected before the calibration completed, and all saved receipts are rescored under the same corrected policy. Rejection reasons motivated the change, but preliminary aggregate success counts had already been seen. This is a documented exploratory correction, not a blinded confirmatory evaluator. Programs requiring non-NumPy imports remain invalid.

For each task and model, `pass@1` is the fraction of the four independent programs that solve every hidden test input; `pass@4` is one if any of the four succeeds. These estimates are descriptive difficulty measurements, not independent population replicates or evidence for an organization effect.

## Pilot selection and interpretation

Once all 3,200 v2 requests have settled, the 40-task P2 pilot is selected from tasks with pooled sample success between 20% and 60%, inclusive (successes among eight samples across the two models). Selection is deterministic and stratified on the maximum input grid area; a SHA-256 tie-break fixes membership. The remaining 360 tasks are withheld from subsequent organization development. They are not pristine untouched test tasks because both calibration models received their training examples and test inputs during this calibration. If fewer than 40 tasks satisfy the predeclared range, no 40-task pilot manifest is issued and the shortfall is reported rather than broadening the criterion after seeing results.

## Evolutionary-search control

The control keeps a finite population of `transform` programs and scores candidates on training pairs only. An LLM mutation operator receives the parent program, its training score and training examples; each mutation consumes one call from an explicit total-call budget. Selection uses training score and a fixed deterministic tie-break, with no spatial neighborhood, differentiation, or developmental rule. Hidden test outputs are used only after the search budget ends. The implementation receives a two-task mock-operator smoke test; no larger evolutionary experiment is part of this work order.

## Evidence limits

The model-generated programs may exploit public ARC task familiarity in model pretraining; the project cannot establish clean training-data provenance for provider weights. Model identity is the served API identifier, not a verified weight digest. Pilot difficulty measured from the same two model APIs must not be presented as a model-independent property of the tasks. Task-level calibration samples cannot be used as independent replicates for the later organization comparison.

These are ARC-derived program-synthesis research measurements, not official ARC Prize scores. The [ARC Prize verified testing policy](https://arcprize.org/policy) evaluates direct task-to-grid predictors without client-side tools, while this project asks models for executable programs and runs an external evaluator.

## Reproduction from preserved receipts

With the archived dataset and private receipt directory available to an authorized reviewer, run the scorer, ledger audit, and pilot freezer in that order. The scorer does not make API calls. Do not put API keys in these commands or copy private response bodies into the repository.

```sh
python3 -m tools.score_arc_calibration --archive "$ARC_ARCHIVE" --private-root "$ARC_PRIVATE_ROOT" --csv reports/p2-arc-calibration-v1.csv
python3 -m tools.audit_arc_calibration --private-root "$ARC_PRIVATE_ROOT" --csv reports/p2-arc-calibration-v1.csv --output reports/p2-arc-calibration-audit-v1.json
python3 -m tools.freeze_arc_pilot --archive "$ARC_ARCHIVE" --csv reports/p2-arc-calibration-v1.csv --output reports/p2-arc-pilot-v1.json
```

The private `scores.jsonl` is append-only and preserves individual failures. The CSV and pilot manifest are public aggregates and task IDs; neither contains hidden answer grids.
