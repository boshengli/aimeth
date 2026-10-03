# Literature and novelty review of manuscript v0.1

Review date: 2026-10-03. Reviewed source: `manuscripts/aimeth/manuscript.md`, SHA-256 `e2aa64f1d4f664aff30b931c5a84358b6175458dce475fde3463fb2a5470a03c`. Review is read-only with respect to the manuscript. Scope: R1–R9 attribution, verification depth, and novelty/emergence wording. The calibration receipts were not independently audited in this review.

## Overall assessment

The cited high-level findings are supported at the stated verification depths. The draft clearly identifies central population results as pending and does not claim demonstrated emergence, mathematical proof, superior collective capability or priority. In particular, the distinction between simulated recovery and physical self-repair for R5 is appropriate. Its discussion that the literature search does not establish priority should be retained.

The manuscript is suitable as an explicitly labelled research proposal and evidence-limited working draft. The literature review does not establish that the proposed developmental mechanism is novel or that the planned baselines exhaust competitive alternatives. Three issues merit action; none calls for inventing additional results.

## Findings and suggested changes

### 1. Agent count does not unconditionally expand computation

**Location:** Introduction, first sentence, line 13 of the reviewed version.

“Increasing the number of computational agents expands available computation” treats an implementation-dependent association as a premise. Under the manuscript's own fixed-resource comparisons, additional logical cells can divide the same allowance and may add overhead without increasing useful or available computation. This is especially relevant when cells share one backend.

**Suggested wording:** “Increasing the number of computational agents changes how computation is distributed; whether it increases useful collective capability depends on resource allocation and coordination.” This aligns the opening with the actual estimand and avoids using cell count as a proxy for compute.

**Severity:** Scientific framing correction before the next draft.

### 2. R9 needs its preprint and version status in the manuscript

**Location:** Introduction paragraph on coordination and reference R9, lines 17 and 155.

The prose's qualitative statement that comparative gains and degradations depend on the architecture–task pairing is supported by the version-3 abstract. However, the bibliography says only “2025” and its DOI, while the cited material is the **8 April 2026 revision, arXiv v3**. The evidence ledger records this correctly, but a reader of the manuscript alone cannot see that this is a preprint or why it differs from the earlier version. Earlier indexed summaries describe 180 configurations/four benchmarks; v3 describes 260/six. No such numerical mismatch appears in the present prose, which is good.

**Suggested wording:** “A recent preprint comparing agent architectures reports both benefits and degradations across tasks…” Cite the record as “2025; revised 2026. arXiv:2512.08296v3, 8 April 2026. Preprint.” Keep the versioned URL. Do not import the older search-snippet statistics.

**Severity:** Provenance correction before manuscript distribution beyond the project.

### 3. High-level verification suffices for this introduction, not the novelty or comparator decision

**Location:** Introduction description of GPTSwarm/G-Designer; Discussion's candidate contribution; future baseline selection.

R7 and R8 were verified through primary proceedings abstracts and bibliographic records, rather than a full audit of their optimizers, supervision, inference protocol and resource accounting. Those sources support the broad statements made. They do not yet justify asserting that the proposed differentiation/proliferation mechanism is absent from all nearby methods or choosing a weakened graph baseline. The present manuscript correctly labels its contribution a candidate and disclaims a systematic priority search; retain both qualifications.

**Suggested actions:** Before claiming a mechanistic advance or freezing confirmatory comparators, inspect the R7/R8 Methods and released implementations specifically for learned node operations, topology construction, adaptation timing, central supervision, agent-count changes and total optimization cost. Use “GPTSwarm optimizes node-level prompts and graph connections” in place of the broader “optimizes computational operations and their connections.” Add a compact distinction table only when these dimensions are verified; absence from an abstract is not evidence of absence from a method.

**Severity:** Evidence gap for future novelty and fair-comparison claims; not a reason to withhold the clearly labelled v0.1 draft.

## Citation-by-citation scope check

| Reference | Current manuscript attribution | Verification depth | Assessment |
|---|---|---|---|
| R1 | Shared local rules grow/repair prescribed patterns | Primary full text, model and training experiments | Supported; externally specified target caveat retained |
| R2 | Local messages support global digit classification | Primary full text, task/model and connectivity limits | Supported; no claim of shape discovery or classifier superiority |
| R3 | Physical swarms form collective morphology locally | Author-institution abstract and bibliographic record | Adequate for this broad attribution; not a mechanistic replication audit |
| R4 | Communicating active-matter models organize across scales | Publisher-indexed aggregation/cluster-analysis sections | Supported; not interpreted as demonstrated intelligence |
| R5 | Hardware decentralized classification; recovery distinguished from physical repair | Author record plus publisher-indexed Methods/Discussion/recovery sections | Supported; simulated/physical distinction correctly preserved |
| R6 | Communication learning under partial observation; centralized training/decentralized execution | Proceedings abstract and author-paper title page | Supported at the stated level; no locally trained or language-only claim |
| R7 | Agent prompts/operations and connections optimized | Primary proceedings abstract | Broad claim supported; tighten operation wording and audit Methods for comparative novelty |
| R8 | Task-conditioned communication topology learning | Primary proceedings abstract | Supported; not identified as autonomous cell development |
| R9 | Architecture- and task-dependent gains and losses | Version-3 author record and abstract | Qualitative claim supported; mark preprint/revision explicitly |

No additional network retrieval was necessary for these limited checks. This review used the already verified primary-source ledger and reference metadata. It does not convert abstract-level checks into full-paper validation or assert that the proposed experiments have been executed.
