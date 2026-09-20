# Compact role prompt storage · post-pilot engineering increment

2026-09-20. Job 196060 executed source 8712fd9 with a separate copy of role prompts for each agent. That source and all scientific results remain frozen in archives/role-pilot-v1. The following storage change was implemented after observing the job; it was not deployed into that experiment.

The current compiler stores four immutable role message templates and one agent-to-template mapping. The generic event store resolves the referenced template when freezing each actual request. It rejects incomplete mappings, missing templates and mixed storage modes. Existing per-agent and legacy shared-base manifests remain supported. Role instructions, graph rules, envelope limits and selection policy do not change.

Validation compares all eight first-round H requests byte-for-byte against the archived executed implementation, then compiles H/F at N=8,32,128,512,10000. The older N=10000 compilation hits the 2 MiB manifest-event bound. The compact version records actual payload sizes and compilation timings in reports/role-pilot-v1/scale-validation.json. This is local engineering evidence, not a token/scheduler/GPU throughput benchmark or 10K model run.

Four rounds at N=10000 imply 40,000 call slots and 37,500 messages. The live role-pilot driver remains intentionally fixed to N=8 for this frozen protocol; increasing it requires a new budget/schedule, input-token accounting, admission/load testing and shared durable recovery. Compiling a manifest does not establish multi-host execution or production readiness.
