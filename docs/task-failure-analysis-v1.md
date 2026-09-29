# M2.3 task failure review and a bounded continuation

This is a post hoc, independent offline review of the frozen M2.3 v2 public records, whose execution source is `7b347be103a7df4b179a41a0482933030fbf35c6`. No historical response, parser, mathematical evaluator, selection, or score is changed. The analysis is reproducible from `reports/role-contract-v2/events.jsonl` and `summary.json`:

```sh
python3 tools/analyze_contract_failures.py --check reports/task-continuation-v1/prior-analysis.json
```

## Observed failures

All 64 responses are parseable JSON and have `finish_reason=stop`. Their reported completion lengths range from 10 to 385 tokens against a 1024-token cap. A cap increase would not directly test the observed failure mechanism.

| Original contract | Valid envelope | Bare task certificate | Other envelope-key failure | Justification too long |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 15 | 7 | 8 | 2 |
| Output card | 25 | 6 | 1 | 0 |

The seven output-card format failures comprise six bare certificates and one object containing only `candidate` and `justification`. Baseline failures also include task/context re-description, copied context wrappers, and extraneous metadata. These are completed answers with the wrong response structure, not network failures or partial JSON. The original 32/32 output-card readiness gate remains failed.

The NS task has 19 format-valid envelopes: nine baseline and ten output-card. Seventeen contain integer certificates rejected by the mathematical constraints; two output-card certificates contain a noninteger field and fail the mathematical certificate schema. All 19 retain their original failure status. The historical totals remain 0/16 NS successes for each contract.

For diagnosis only, inspecting a directly present `candidate` object or an exact bare certificate finds such an object in 30 of the 32 NS responses. All 30 also fail the unchanged mathematical evaluator; five contain a noninteger value. The other two responses reproduce context/task material without a direct certificate. This inspection does not admit malformed envelopes or replace historical scores. It shows that repairing the outer JSON envelope alone cannot make these recorded NS answers mathematically valid.

All eight output-card NS responses with empty context return the same negative signs for the velocity and time exponents. Since the task explicitly rescales the spatial argument by `lambda*x`, these are not an equivalent inverse-coordinate convention. Several justifications write down a correct balancing equation and then give values that do not satisfy it. Others confuse the pressure exponent with the exponent after taking a spatial derivative, add a derivative to the forcing term, or apply a squared-norm change of variables to the unsquared L3 norm. Some candidate fields also disagree with the model's own justification.

## Mathematical and protocol assessment

An independent chain-rule and change-of-variables review found the NS task's integer requirement satisfiable. The evaluator's time, transport, viscosity, pressure-gradient, forcing, squared-L2, and unsquared-L3 constraints match the stated rescaling. No mathematical evaluator defect was found in this failure set. This review is limited to the scaling-algebra certificate; it is not verification of a derivation supplied by the model or of Navier-Stokes regularity. Exact answer keys are intentionally not reproduced in this report.

There is a wording problem worth testing prospectively. The NS user task says to return only the six task fields, while the system prompt and appended output card require those fields inside `candidate`. The system prompt already says the outer envelope takes precedence even when a task asks for a standalone certificate, so the recorded behavior is not proof that the contract is logically impossible. Nonetheless, leaving two different output descriptions in the same request is avoidable. A new experiment can test whether a single consistent description improves compliance without changing the mathematical problem or evaluator.

Recorded contexts cannot isolate an effect of agent organization. For NS, the E0 recorded fixture has no usable candidate; the E1, critic, and synthesizer fixtures contain different incorrect generated algebra. These were frozen source-selected fixtures, not independent mathematical reference answers. Repeating errors in their presence is compatible with anchoring but does not establish its cause. Empty-context errors demonstrate that bad peer content is not the sole explanation.

The actual paired requests use matching wire seeds in all 32 pairs. The service reports one common fingerprint, but neither seed determinism nor the exact model weights are independently established.

## Smallest useful new submission

Use a new, frozen 16-call developmental comparison: two served model IDs, two public development tasks (prime counterexample and NS scaling), two contracts, and two repetitions. Hold the role at E0 and context empty. The control is the original output-card request. The treatment replaces only the user task's standalone-output sentence with a sentence identifying the task fields as fields inside `candidate`; retain the existing system envelope and output card. Keep model options, output cap, parser, evaluator, task mathematics, and stopping rules fixed, with paired seeds and randomized paired order.

This design distinguishes format improvement from mathematical improvement while retaining the prime task as a solvable control. It provides no independent population runs, no H/F organization comparison, and no frontier-mathematics result. It is not powered for a general superiority claim. A transport failure and every unstarted cell must remain visible; retries or repaired outputs must not be silently added. Freeze admission criteria for any later multi-round experiment separately rather than inheriting or relaxing the failed historical gate after observing results.

The offline analysis and mathematical evaluator stay outside model request content and generator retrieval. Only the frozen public task statement, role, context, and chosen output instruction enter the new request.
