# Offline developmental-policy fixture v0

3 October 2026 · **Proposal for review; not frozen, implemented or launched.** Executable-field source: `plans/cell-development-pilot-v0.json`.

This small fixture makes the manuscript's local-rule terminology implementable without model calls, credentials or changes to v8. It checks software behaviour. It is not a mathematical benchmark, a 10K population experiment or evidence of emergent intelligence.

## One fixture and four modules

Eight synthetic obligations ask for a colour token whose salted SHA-256 matches a public target digest. Each domain contains four tokens. The constructor must enumerate its assigned indices; the checker evaluates the predicate. The generator sees only the public obligation and its local history. The separate fixture builder/verifier knows the expected witnesses; that mapping is never a module input. Three deterministic seeds support implementation cases, not statistical replication.

| Module | Local action | Committed consequence |
|---|---|---|
| `construct` | Select next untried candidate from an owned obligation/shard | Advance its cursor; place candidate in local unchecked queue |
| `check` | Evaluate one candidate against the public digest predicate | Retain negative evidence or emit a valid-witness artifact; hash acceptance alone is never semantic validation |
| `route` | Send one outbox item along a recorded edge using current endpoint versions | Apply the typed contract signal; only an accepted delivery grants payload/artifact access |
| `divide` | When at least two unresolved owned obligations remain, create one daughter if bounds permit | Inherit exact contract state; transfer one obligation's remaining shard through an explicit parent–child signal |

A deterministic round-robin scheduler grants one turn per living cell per sweep. Priority is unchecked candidate, outbox, eligible division, construction, then idle. Newborns enter the next sweep. Preparation and delivery are synchronous in the normal fixture; the stale-message case deliberately breaks that assumption to verify rejection. It must not silently rebase or resend.

The developmental fixture starts with four seeds on an imposed reciprocal ring and permits at most sixteen cells. A daughter receives reciprocal parent edges only. No rewiring or coordinates are introduced. Division transfers the lexicographically greatest eligible obligation; a parent locks it until the handoff succeeds, and retains it if delivery is rejected. Empty daughters remain visible and cost memory; they are not silently deleted. The cap is a bound, not a target.

## Contract integration boundary

The existing `CellContract` has no memory-edit operation. Its memory therefore remains immutable genesis input. Queue state, cursors, ownership, selected modules and processed messages require a **separate bounded policy journal** with deterministic replay. Do not write private contract fields. A combined transition validates detached contract and policy states before committing both; rejection must preserve both. This is an implementation requirement, not a claim that the journal already exists.

Contract expression gates initially permit all four modules. Per-turn selected-module activity is separately recorded as a one-hot vector; it is not a learned gene programme. Rolling activity fractions require eight non-idle actions and otherwise return `null`. The fixture cannot establish stable differentiated cell types from these activity records. At division, a daughter inherits exact contract memory/expression and receives mutable task assignment only through the logged handoff.

Version identifiers cover the run card, fixture, contract snapshot and policy journal. Every combined snapshot records their hashes and the joint event head. Initially this is single-writer and in-memory; durable crash recovery is a separate required implementation and verification step.

## Comparators and resource accounting

| Arm | Start / bound | Assignment and communication | Interpretation |
|---|---|---|---|
| Development | 4 / 16 | Two obligations per seed; local division and handoff; ring plus lineage edges | Whole-policy fixture behaviour |
| Fixed | 16 / 16 | Two cells per obligation split candidate indices by parity; reciprocal ring | Competitive explicit allocation without developmental overhead |
| Independent search | 16 / 16 | Same nonoverlapping shards; no peer messages; local construction/checking; terminal witness union | Sampling/aggregation reference |
| No division | 4 / 4 effective | Same initial assignments and ring as development | Matched-start policy contrast, including division overhead and reassignment |

All use identical predicates, candidate order, module implementations, verifier and named resource ceilings. No arm receives tuning in this fixture. Idle cells are accounted for but are not forced to make useless calls. Fixed and independent arms receive productive nonoverlapping shards rather than a deliberately wasteful baseline. Starting population differences limit the first contrast; the matched-start arm does not independently identify a structural mediation effect either.

The card bounds turns, module actions, construction, checking, route attempts, births, bytes, events and snapshot size separately. Existing contract charges remain one synthetic unit per accepted signal and two per division. Rejected attempts still appear in the policy attempt ledger. Terminal verification has the same separate allowance across arms and returns no hint to cells. Unused allowance is reported and cannot be reassigned silently. These are synthetic counters, not prices, tokens, FLOPs or equal hidden model computation.

The allocation is explicit: satisfiable and unsatisfiable cases cover all four arms; duplicate/stale message cases cover only the three communicating arms. Across three seeds this gives 42 allocated software cases. Independent-search message-fault cases are not allocated and are never reported as passes.

Stop on verified completion, a fully idle/exhausted sweep, the first resource bound, or an integrity error. Preserve all allocated arm–seed–condition cases, including crashes and unfinished cases. The unsatisfiable fixture should end with an unresolved obligation. Duplicate and stale fixtures should reject the injection without partial mutation; they count as successful software checks when rejection behaves as specified.

## Falsifiable outputs and remaining scientific decisions

Record at genesis, every sweep and termination: node/edge counts, weak components, outgoing-degree distribution, maximum lineage depth, births and the fraction of lineage-added edges. These descriptors distinguish imposed ring edges from generated lineage edges; they are not layers, tubes or spheres. Optional degree-preserving graph randomizations are descriptive nulls only. They are not a performance intervention or evidence for structural mediation.

The implementation fails its contract if ownership overlaps after a handoff, a cell reads another cell's unreceived state, a rejected event partly commits, replay changes the next action, an unsatisfiable obligation receives a fabricated witness, or denominators omit failures. A correctly implemented policy may produce no advantage, extra overhead or no persistent activity differentiation. All are admissible outcomes.

For a real 10K candidate, the card deliberately leaves required decisions as `null`: actual task sampling and protected evaluation; model/revision; gene mapping and code; initial graph and developmental rules; population schedule; replication/precision; provider-specific bounded calls, outputs and spending; comparable baseline tuning; fixed-work and structure-specific interventions; stopping, recovery and analysis. Null values prohibit treating the card as a launch-ready population protocol. They introduce no single-Agent success prerequisite. Root review should first decide whether this fixture's exact policy and journal requirements are appropriate to implement.
