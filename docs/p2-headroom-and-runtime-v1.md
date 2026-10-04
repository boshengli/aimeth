# P2 · Agent runtime and task headroom (2026-10-04)

Status: exploratory engineering and calibration. No organisation comparison has been run yet; nothing here is a
capability claim about developmental organisation.

## 1. Runtime (`aimeth_rt/`, `tools/rt_run.py`, `tools/rt_grade.py`, `tools/evald.sbatch`)

* **Evaluation service.** A daemon inside a Slurm job on GPU08 (no internet) claims program files from a shared queue
  (`/data/libs/aimeth/rt/evalq`) and runs each in a bwrap sandbox: no network, no API keys, no answer keys mounted;
  static identifier screen first. Only agent-visible information is returned: ARC training-pair correctness and the
  program's own training outputs; for callus imputation, the score on a pseudo-task built from the target section's own
  visible genes (same number of genes hidden at random, seed per replicate). Test predictions go to a private directory and
  are graded afterwards by `rt_grade.py`. Smoke tests: identity/raising/forbidden-import ARC programs and one DeepSeek
  imputation program behaved as expected. Queue latency is about 30 s per evaluation (NFS v3 attribute caching between
  login node and GPU08; GPU08's clock is ~21 min behind the login node).
* **LLM layer.** One AIMD limiter per process; rate-limit rejections are retried, anything else counts as a spent call and
  is never resubmitted. Paid providers carry a hard budget stop on a conservative envelope (10 CNY/USD, peak list prices);
  the check runs before each call, so in-flight calls can overshoot by a few yuan (observed: 44.5 vs 40).
* **Workflows (single-agent controls, budget = n calls).** `independent`: n samples of the initial prompt, final = best
  visible check. `self_repair`: one conversation, visible check returned as feedback each round, final = best visible check.
  Both stop early on a train-perfect ARC program.
* **Extraction rule (added 17:50 after observing it).** deepseek-flash sometimes ends with the final code block inside the
  reasoning stream and an empty answer — 13 of ~80 self-repair turns, 0 of ~70 independent turns. Both arms now take the
  last complete code block from the reasoning stream when the answer is empty (`code_source = reasoning_fallback`). The
  self-repair bio run started under the old rule was stopped and kept as
  `bio-self_repair-ds-r0.v1-aborted-extraction.jsonl`; the arm was restarted from scratch.

## 2. ARC headroom with deepseek-flash (thinking, reasoning_effort low, as in the calibration)

| Set | Max tokens / call | Tasks | Solved (1 sample) | Truncated | Note |
| --- | --- | --- | --- | --- | --- |
| ARC-AGI-1 pilot-40 (Codex freeze, 20–60 % pooled at 12,288) | 32,768 | 40 | **39** | 0 | pilot is saturated |
| ARC-AGI-2 evaluation | 32,768 | 120 | **24** (20 %) | 86 | 24 / 34 non-truncated solved |
| ARC-AGI-2, 20 of the truncated tasks | 131,072 | 20 | **5** | 0 | median 59k completion tokens |

Envelope cost: 2.9 + 44.5 + 13.3 CNY. Grades: `/data/libs/aimeth/rt/runs/*.graded.jsonl`.

Reading. With this model, ARC difficulty is dominated by the per-call token limit, not by failure to find the rule
once reasoning finishes: the frozen ARC-1 pilot's 20–60 % band came mostly from truncation at 12,288 tokens (Codex's
sensitivity audit: 43 % of DeepSeek samples truncated, 87 % success when not truncated). Consequences for P2:

1. ARC-1 pilot-40 cannot discriminate organisations for deepseek-flash at ≥ 32k tokens per call (ceiling).
2. ARC-AGI-2 has headroom (≈ 20 % at 32k; extrapolated ≈ 38 % for one 131k call).
3. Budgets must be matched in **tokens**, not only calls, and a **single long call with the same total token budget** must
   be a control arm: otherwise an organisation can win simply by spending more reasoning tokens in total.

## 3. Callus imputation pilot (running)

36 tasks × {independent, self_repair} × 4 calls, deepseek-flash, reasoning_effort medium, 65,536 max tokens, one replicate,
budget stop 60 CNY per arm. Results will be graded with `rt_grade.py` (answer keys) and compared per task.
