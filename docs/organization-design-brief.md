# M2 · Agent organization design brief

Status: ready to start design, not a frozen design or launch authorization. Prepared 2026-09-14 from protocol v0.1 and the user's emphasis on organization. No claim that one architecture wins.

## Inputs that are ready

- Research question: verifiable mathematical output under a declared common resource budget.
- Experimental unit: an independently initialized population run on a task instance; agents/messages are dependent observations.
- Separate model generation, in-population criticism, final candidate selection, and independent terminal evaluation.
- Record an organization as graph over time, roles, messages, memory, selection, verification, and scheduling policy.
- Four candidate controls: S (one sequential agent), I (independent population), L (local group communication), X (local plus cross-group communication).
- Known engineering risks are recorded; model, context window, memory, and compute limits are not assumed verified.

## Six design decisions and their outputs

| Decision | Question | M2 artifact |
|---|---|---|
| Agent state | What persists across calls, and what triggers the next action? | State-transition specification; step/event identity |
| Roles | Which roles explore, criticize, integrate, and verify, and which are held fixed? | Role/information-access matrix; explicit cost accounting |
| Communication | Who can send what, to whom, at which times? | Directed graph policy, message schema, quotas, delivery order |
| Memory | What is private, shared locally, shared globally, or evaluator-only? | Access rules, summarization policy, source attribution |
| Selection and error control | How are useful lemmas promoted and invalid claims retracted? | Candidate/evidence statuses, fixed terminal candidate limit, correction propagation |
| Comparison | Which single variable does each contrast change? | Arm matrix, matched budgets, ablations, metrics, frozen pilot plan |

## Starting design to develop

Use S/I/L/X as controls before expanding the candidate family. S tests serial depth; I tests multiple independent trajectories; L tests local information exchange; X tests redistribution of an equal edge/message budget across groups. Hierarchies, dynamic routing, blackboards, heterogeneous models, and biological spatial analogies can become later hypotheses with their own controls.

In the M1 HTML, the optional diagram uses 32 population nodes, four groups of eight, and degree-two channels for L/X. X uses degree-preserving edge swaps. This is an explanatory candidate graph, not a frozen protocol, a claim of connectedness/optimality, or a measurement of performance. It visualizes a fairer graph comparison: same node count, degree, and edge count. Runtime messages still require directed delivery rules and matched token budgets.

Keep the same role allocation, generator model, task material, and final selector across I/L/X at first. If L/X add dedicated critics or coordinators, either assign the same roles in I or label the contrast as a composite organization intervention. Include each role's cost within the same total budget.

Do not claim a pure topology effect when changing graph, roles, memory, prompts, and judge simultaneously. Prefer an ablation that replaces useful content with a declared control or changes links while preserving degree/communication budget. An observed association between diversity and success alone does not establish mechanism.

## M2 acceptance

1. Each arm is executable from an unambiguous configuration, including topology seed and realized graph, roles, message timing, budgets, and stops.
2. A local, model-free trace replay verifies sender/recipient permission, message quotas, event ancestry, and equal intended budget rules across the matched graph contrast.
3. The design states independent repetitions, success/refutation/technical-failure categories, evaluation visibility, and the exact effect each contrast estimates.
4. The output includes an organization diagram, comparison table, role/prompt specifications, trace examples, and an M2 HTML report with evidence and unresolved choices.
5. Pilot task-set, numeric budget, and sample-size choices remain provisional until the appropriate development evidence exists; no design diagram is passed off as a live result.

Cluster SSH, actual model/container, and the spending ceiling are needed before launch. They do not block specification-level organization design. The immediate next scientific decision is which mechanism to test first: information exchange, specialization, or verification allocation; the protocol's starting proposal is information exchange.
