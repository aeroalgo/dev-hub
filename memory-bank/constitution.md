# [dev-hub] Workflow Constitution

- **version:** 1.0
- **date:** 2026-08-28
- **scope:** dev-hub workflow, its role commands, hooks, and memory-bank artifacts

## MUST

### MUST-1 — TDD first

BACK IMPLEMENT writes or updates targeted tests before production code. The red → green → refactor cycle is mandatory; Python tests use `.venv/bin/pytest` from the repository root.

### MUST-2 — No silent fallback

A workflow must fail closed when a required dependency, path, marker, or configuration is missing. It must report the failure instead of silently selecting an unverified alternative.

### MUST-3 — FRONT tests parent-only

Only the parent agent may run frontend test runners, including Vitest, RTL, Playwright, `npm test`, `pnpm test`, and E2E commands. Subagents may inspect or edit test files when assigned, but must never run those runners.

### MUST-4 — Lean load

Within one role session, each workflow rule or skill file is read at most once. Re-read is allowed only when an explicit offset or an external change makes the earlier content insufficient. Load only the active work shard and its routed context.

### MUST-5 — Fail-closed misconfiguration

Invalid or ambiguous environment and configuration values are errors. Do not invent defaults, coerce malformed values, or continue with a guessed project, role, path, model, or execution mode.

### MUST-6 — No-guess markers

When evidence is insufficient, preserve the uncertainty explicitly with `CLARIFY`, `NEED_HUMAN`, or another defined workflow marker. Never infer a missing requirement, owner, route, status, or dependency from naming alone.

### MUST-7 — ONE Handoff per step

`memory-bank/activeContext.md` contains exactly one current `## Handoff` block for the active step. Replace the previous handoff on FINISH; do not append a second block or hide history beside the current navigation state.

### MUST-8 — §0.11 integration parity

Every INTEG feature must be wired end to end: the user-facing element, frontend client, backend route or service, and persisted or external data contract must have matching evidence. A missing counterpart is a defect, not an optional follow-up.

### MUST-9 — Phase authority

`ANALYZE` is the read-only authority check before implementation, and `AUDIT` is the intent-to-implementation authority check after implementation. Findings must be recorded in their role artifacts; a later phase must not silently replace either check.

## SHOULD

### SHOULD-1 — Outcome-first titles

Step and shard titles should describe the user or system outcome, not only an infrastructure slug.

### SHOULD-2 — Kill is success

A killed idea pipeline should retain its rationale and be treated as a successful decision outcome, not as an implementation failure.

### SHOULD-3 — Verify replacement cleanup

After deleting or replacing a path, symbol, fallback, or entrypoint, use `rg` and import-audit evidence to confirm that no live callers remain before declaring the step closed.

## Note

The hub version is the canonical starter. Product repositories may copy and adapt these rules, but any adaptation should preserve the fail-closed, evidence-first workflow intent and state its scope explicitly.
