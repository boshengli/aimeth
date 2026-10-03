# Biological inspiration and design provenance: source audit v0

Audit date: 2026-10-03. Scope: identify the pepper paper and trace the layered/vascular computational designs. This is a source audit, not a reanalysis of biological data or a validation of an AI mechanism.

## Identified primary publication

**Han, J. et al. (2026). Laminar patterning transcription factors orchestrate spatial metabolite partitioning in Capsicum fruit. Nature Plants 12, 1095–1115.** Published online 5 May 2026. DOI: [10.1038/s41477-026-02293-w](https://doi.org/10.1038/s41477-026-02293-w).

The title, authorship, journal, year, volume, pages, publication date and abstract were checked against the [publisher's article page](https://www.nature.com/articles/s41477-026-02293-w). The public page presents subscription-preview content; the detailed assessment below uses the user-supplied local publication PDF, not an assumed full-text web retrieval. Its filename says “Nature Pants”, but the journal is **Nature Plants**.

Local PDF: `0013-Workflow/S0001-Layer/za/02.2026.Nature Pants.Pepper LPTF.pdf`; 44 PDF pages; SHA-256 `8712292c6d9f9c63ca1ff47b433e8df26ab284d61d4f0c991a6db53d629e6776`. Pages below distinguish PDF positions from printed article pages.

## What the publication supports

| Paper content and location | Evidence category | Appropriate use and boundary |
|---|---|---|
| The atlas combines 121,070 nuclei from 14 snRNA-seq datasets and 211,398 spatial cell-bins from 43 ST datasets, totalling 332,468 profiles across 57 samples. PDF p. 2 / article p. 1096; Fig. 1. | Reported data generation and computational integration. | Supports a substantial spatial/transcriptional resource. It does **not** describe 332,468 equivalent physical cells from one organ, 57 independent treatment replicates, or an experimentally established computational population threshold. |
| Anatomical layering aligns with transcriptional patterning in several tissues. Some leaf and fruit vascular bundles, pith and other regions lack clearly resolved layering in these data. PDF p. 4 / article p. 1098; Figs. 1–2. | Spatial observation plus annotation; explicit resolution limitation. | Motivates heterogeneous spatial organization. Do not impose a universal layered template or interpret failure to resolve layers as proof of their absence. |
| Gland populations have distinct capsaicin-related expression patterns; MYB31/WRKY9 localization is supported by spatial expression and smFISH. Pseudotime suggests a developmental sequence. PDF p. 8 / article p. 1102; Fig. 4. | Localization and computational association; inferred trajectory. | Supports a division-of-function analogy. A pseudotime sequence is not lineage tracing, and co-expression is not a measured intercellular transport or signalling event. |
| Exocarp regions differ in photosynthetic, pigment and starch-related expression. WRKY6, ZAT10 and BTF3 were nominated from spatial/co-expression analyses. Silencing affected pigmentation, transcripts and capsanthin content; Y1H and reporter experiments support particular regulator–promoter relationships. PDF p. 10 / article p. 1104; Fig. 5 and Extended Data Fig. 8, caption at PDF p. 36. | Observations, computational nomination and targeted perturbation/assays, with different strengths of evidence. | Stronger than localization alone for the tested regulators. These experiments do not isolate the causal effect of tissue geometry independently of gene activity, nor establish that the entire architecture self-organizes from a minimal local rule. |
| The cross-species workflow reports 365 LPTF candidates from eight stratified systems in five species. PDF p. 12 / article p. 1106; Fig. 6. Discussion explicitly retains a need for functional validation. PDF p. 14 / article p. 1108. | Computational prediction and comparative interpretation. | Cite them as candidates, not 365 experimentally validated master regulators. Conservation of a general mechanism remains a hypothesis. |
| The Discussion proposes interpreting organs as assemblies of layer-associated regulatory circuits and suggests future promoter editing. PDF p. 14 / article p. 1108. | Authors' mechanistic interpretation and future experimental proposal. | Motivates a modular computational analogy. It is neither an implemented multi-agent algorithm nor empirical evidence of higher intelligence. |

This audit inspected the relevant publication text and figure captions, not raw matrices, image quantification or supplementary table entries. Consequently, numerical effects and biological conclusions above remain **source-reported**, not independently reproduced by AIMeth. Detailed regulatory-effect magnitudes are unnecessary for the current AI claim and should not be copied into the manuscript without a targeted figure/source-data check.

One local source consistency issue should remain visible if detailed regulator assays are cited: the Results and Extended Data Fig. 8 caption describe ZAT10–PSY1 and BTF3–CCS Y1H relationships, whereas the Y1H Methods paragraph at PDF p. 15 names BTF3 and WRKY6 prey CDSs. This audit does not resolve that construct-description mismatch. The high-level spatial/functional inspiration does not depend on choosing an unverified resolution.

## Where the Agent designs enter the chain

| Design source | What it specifies | Attribution for an AIMeth manuscript |
|---|---|---|
| `S0001-Layer/za/S0001-DPV4/20260810_层状Agent分析架构设计_DPV4.md`, §§0–2, particularly lines 80–138. | Explicit reconstruction linking the paper to a 10×10 analysis lattice, four Observers and one Chief. Rows and columns represent biological layer/time combinations; local communication and additional long-range routes are proposed. | A project design document dated 2026-08-10, inspired by the paper. The 100 lattice positions, monitoring hierarchy, communication probability and convergence thresholds are engineering choices, not findings of the pepper study. “100 groups of 100 Agents” is a later extension, not this source's original population count. |
| `S0001-Layer/SLCW_Runtime_v0.1/spec/SLCW_Final_DiscoveryTissue/ARCHITECTURE.md`, §§3–7. | Adaptive Analysis Tissue may specialize/proliferate; Patterning Agents allocate diversity; Interface Agents inspect cross-module relations; a Vascular Network carries selected long-range payloads; Observers form around scientific communities. | The richer computational design explicitly adds developmental and transport-like functions. It is a specification; naming a role does not establish an implemented independent Agent or demonstrate functional emergence. |
| The same specification's `FINAL_DECISIONS.md`, D9–D10. | The fixed 10×10 grid is retained as compatibility/execution structure; stopping is operational and is not proof of scientific truth. | Supports avoiding a forced fixed geometry and separating convergence from evidence. These are local design decisions, not biological laws. |
| AIMeth `docs/slcw-source-realignment-v1.md` and `docs/slcw-math-mapping-v2.md`. | Prior source-to-implementation audit; identifies partial implementations and distinguishes routing/software labels from autonomous regulatory Agents. | Reuse the audited distinction when positioning current implementation. This new source audit did not rerun those historical implementations. |

The user's “微管束” is most closely matched by **Vascular / 维管** in the recovered specifications. A vascular tissue analogy should not be silently relabelled as a cytoskeletal microtubule mechanism. The present evidence identifies the project's terminology; it does not prove that a specific biological transport rule has been transferred into code.

The local LUNA literature evidence table was useful for locating relevant sections, but it is a secondary reconstruction. The publication was read directly before accepting the claims above. Likewise, a DPV4 heading such as “TF = layer identity determinant” is stronger than the reported discriminatory-expression analysis alone supports and should not be imported as an established causal equivalence.

## User analogy versus present implementation proposal

The user's scientific hypothesis is that regulating numerous computational cells can produce mesoscopic and tissue-like organization that improves task capability. That hypothesis is inspired by biological organization; the pepper publication does not test it. Equating metabolite accumulation with intelligence would conflate a biological output with an unmeasured computational capability.

The current implementable mapping is therefore deliberately operational: a cell is a persistent bounded compute unit; an artificial gene is a named, measurable, perturbable module; expression is module activation; a developmental signal is typed information that can alter local state. Layer- or tissue-level specialization is an outcome to measure. These are AIMeth proposals, not biological identities. A raw model weight is not automatically a gene, and no gene-to-weight correspondence was established by this audit.

The offline cell-contract prototype tests state transitions and causal-message bookkeeping only. It neither recreates pepper development nor demonstrates spontaneously forming layers or a capability advantage. Those stronger claims require independently repeated, resource-matched population experiments and interventions on organization or signalling.

## Manuscript-ready positioning paragraph

> Spatial studies of pepper development connect tissue organization with localized transcriptional programmes and specialized metabolism, including layer-associated regulators of pigment biosynthesis (Han et al., 2026). These observations motivate a computational hypothesis: task-conditioned regulation of persistent units may produce specialized organizations that improve collective problem solving. We operationalize this analogy through independently perturbable modules, local state and typed signals. The biological study supplies a design inspiration, rather than evidence that the proposed computational mechanism is effective. Demonstrating that mechanism requires comparisons that separate imposed geometry, locally generated structure and independently measured functional improvement.

## Source provenance and search boundary

Searches were limited to registered AIMeth references/audits and filenames plus selected scientific/design documents inside `0013-Workflow`. No conversation archives, authentication scripts, credentials, remote cluster access or evaluator-only reference files were read. The local PDF was inspected through metadata and extracted complete relevant pages; no additional PDF copy was made. The publisher page was checked on 2026-10-03. This is a focused identification audit, not a systematic review of all biological inspirations.

Local design-source SHA-256 values, paths relative to `0013-Workflow`:

- DPV4 layered reconstruction, path above: `2af280a44a912ce55e305bec56014960a00e627783c50ab2c7eab6275736ab84`.
- `S0001-Layer/za/S0002-LUNA/reports/20260810_论文层状结构证据表_LUNA.md`: `f11dda897ab3917b663a17011f6ad182ed2cc1269b34e3d4360df00c33325148`.
- Final DiscoveryTissue `ARCHITECTURE.md`, path above: `6dce7f37e5e7486fa5ee144803dc6e03a23713add01e2c22baf3eeabbfe167d9`.
- Final DiscoveryTissue `FINAL_DECISIONS.md`, path above: `53b506b7eb3bbd7b4351f324a8dc74a0f46964cb8679d9d64be926f01a4cecb7`.

Full local source root: `/Users/ba/Library/Mobile Documents/com~apple~CloudDocs/AI_agent/Projects/0013-Workflow/`. Original source documents remain there; this audit does not authorize deployment or replace the current experimental protocol.
