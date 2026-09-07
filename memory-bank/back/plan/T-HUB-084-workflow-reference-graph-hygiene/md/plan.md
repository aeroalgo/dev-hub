# T-HUB-084 — Workflow reference graph hygiene

**Дата:** 2026-09-07 · **Режим:** BACK PLAN · **Уровень:** L3 · **Статус:** draft
**Clarify:** Phase 0 skipped — post-cutover graph cleanup is bounded. **Prompt:** [md/prompt.md](prompt.md)

## WHAT

After prior cutovers, eliminate duplicate direct/transitive `@` edges while retaining one owner edge with explicit load timing. Priority: behavior-first in DECOMPOSE, analyze core, clarify orchestration/PLAN, DECOMPOSE/VAN/CLARIFY/REFACTOR transitive pairs. Remove only proven dead `back-audit.mdc`; classify other zero files.

## FR / AC

- **FR-001:** each active W declares a shared dependency once.
- **FR-002:** A→B plus W→B has one owner selected by lazy timing and semantic responsibility.
- **FR-003:** graph validator reports direct duplicate, transitive ambiguity and dangling dead reference.
- **FR-004:** priority mode semantics remain; dead audit cheatsheet has no active caller.

1. Duplicate edge fixture fails with both lines.
2. Removing sole owner fails; removing redundant edge passes.
3. PLAN/DECOMPOSE/ANALYZE markers remain.

### AC−

- No inlining large shared policy, archive rewrite, blind `rg` deletion, or compatibility alias.

## HOW / Eng spine

```text
W -> A -> B and W -> B  =>  one declared owner edge + explicit timing
```

TM-084-01 direct duplicate; TM-084-02 transitive owner; TM-084-03 priority markers; TM-084-04 dead link; TM-084-05 archive exclusion; TM-084-06 full suite.

## Replacement / sunset

| Kind | Legacy | Replacement | Policy |
|---|---|---|---|
| A | repeated/transitive active edges | one owner edge + validator | delete in-epic |
| A | `back-audit.mdc` | absent after caller scan | delete in-epic |
| C | duplicate link as safety fallback | fail-closed owner validation | delete in-epic |
| I | stale active `@` mentions | canonical dependency declaration | delete in-epic |

## Review readiness

Product probe, Eng spine, delivery closure and QA matrix: **done**; dependencies 081–083 explicit.

## Draft stages

1. edge inventory/red fixtures; 2. ownership rewrite; 3. proven dead cleanup; 4. validator/mode suite/sunset scan.

## Следующий режим

→ **BACK DECOMPOSE T-HUB-084-workflow-reference-graph-hygiene**
