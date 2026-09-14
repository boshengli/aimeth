# Milestone reporting policy

Effective 2026-09-14, confirmed by the user. This supplements the original publication contract without changing its archived baseline.

Every completed project milestone must deliver a versioned, human-readable HTML report. Markdown, logs, JSON, and commits remain the underlying evidence, and do not replace this report.

## Required sections

1. Milestone identity, date, version, scope, and a clear outcome.
2. User requirement → design/implementation → evidence → remaining gap.
3. Completed work, actual validation, negative findings, and unverified items.
4. Source/data/code identities; distinguish baseline commit from the report's delivery commit.
5. Scientific interpretation and limitations appropriate to the milestone.
6. Readiness for the next milestone: ready to design, ready to implement, and ready to run are separate judgments.
7. Next decision, deliverables, and acceptance criteria.

Use explicit labels such as implemented, locally verified, specified, proposed, and untested. Do not present a design document as a completed runtime, tests as scientific validation, or a planned comparison as measured performance.

## File and review contract

- Store HTML and its structured content/evidence under `milestones/`. Use `m<id>-<name>-v<version>` filenames.
- HTML must be self-contained for essential content and usable offline, with embedded CSS/JS and no external runtime dependencies. External citations and optional source-file links are allowed.
- Provide readable desktop/mobile and print layouts, clear navigation, accessible labels, and evidence details. Interaction must not be necessary to read the core conclusion.
- Check content against the original records; render in a browser and check main interactions plus narrow/desktop layouts. Record what was tested.
- Commit the report, its source content, reproducible builder/template, and content hashes. Keep the previous milestone's source snapshots/manifests valid; a correction creates a new report version.
- At handoff, update the project status, decisions, artifact index, and provide a clickable HTML link. Open its preview when practical.
- This is a completion gate, not a timed reminder or a recurring automation.

## Milestone numbering

M1 = research foundation and evidence rules. M2 = agent organization design. M2 may proceed before cluster access, while actual run readiness remains gated by engineering/environment checks. The older protocol's P0–P5 labels are execution phases; M1 corresponds to P0, and M2 is a design milestone spanning preparation for P1/P2. Do not silently rename the archived protocol.
