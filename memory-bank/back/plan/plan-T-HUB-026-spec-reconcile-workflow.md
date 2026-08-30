# [T-HUB-026 | spec-reconcile-workflow] PLAN

**Дата:** 2026-08-30  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-spec-maturity-epics.md](roadmap-spec-maturity-epics.md)  
**Queue:** [roadmap-spec-maturity-epics.queue.yaml](roadmap-spec-maturity-epics.queue.yaml)  
**Deps:** нет hard. Soft: T-HUB-024 (parser reuse).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · brainstorming

→ [decompose-T-HUB-026-spec-reconcile-workflow/index.md](decompose-T-HUB-026-spec-reconcile-workflow/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** лёгкий read-only режим **BACK RECONCILE** + CLI `reconcile-spec` для периодической сверки plan as-built claims ↔ repo reality без full AUDIT; добавить **appetite** fields в plan/decompose schema (timebox, cut_list).
- **gap (as-built):** spec drift после hotfix/вне эпика не ловится до full AUDIT; нет timebox/cut criteria на эпик; RECONCILE mode отсутствует в mainrule router.
- **refs:** `.cursor/rules/mainrule.mdc`; `.cursor/templates/plan.md`; `.cursor/templates/decompose/epic-step.yaml`; T-HUB-012 AUDIT (heavy); chat gap-analysis 2026-08-30.

**CREATIVE need:** нет.

---

## Цель

Оператор запускает `BACK RECONCILE <epic_id>` или `reconcile-spec` после BUGFIX / между эпиками и получает drift report (missing files, stale as_built, orphan tests) за минуты — **read-only**, без implement yaml mutation.

---

## Продуктовая speка (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как tech lead, я хочу reconcile report после hotfix, чтобы plan/decompose не врали про as-built. | P0 | Fixture: as_built claims file X → file deleted → RC-001 HIGH |
| US-002 | Как loop-оператор, я хочу `BACK RECONCILE` в router, чтобы не гонять full AUDIT для drift check. | P0 | mainrule table includes RECONCILE → workflow file exists |
| US-003 | Как PM, я хочу appetite block в plan (timebox, cut_list), чтобы scope circuit breaker был explicit. | P1 | plan template has Appetite section; decompose index optional mirror |

#### Acceptance Scenarios — US-001

- **Given:** decompose s02 `as_built` lists `src/foo.py`; file removed in repo
- **When:** `reconcile-spec --plan-id T-xxx --cwd $PROJECT_ROOT`
- **Then:** finding RC-001 severity HIGH; exit 0 (report only) or 1 with `--strict`

### Functional Requirements (FR-###)

- **FR-001:** New workflow `.cursor/rules/back_developer/workflow-reconcile.mdc` + lean gate `_lean/reconcile.mdc` — STRICTLY READ-ONLY (like ANALYZE).
- **FR-002:** Register `BACK RECONCILE` in `back_developer/mainrule.mdc` command table.
- **FR-003:** CLI `reconcile-spec` in `epic_resolve.py` (or sibling) — `--cwd`, `--plan-id`, `--format text|json`, `--strict`.
- **FR-004:** Checks: (a) each `as_built` path in decompose exists or marked deleted in completed implement `deletes`; (b) each `delta` path touched should exist post-epic if step completed; (c) plan `files` / HOW table paths exist; (d) optional constitution presence (soft).
- **FR-005:** Reuse traceability parsers from T-HUB-024 when merged; duplicate minimal parser OK if 024 not done.
- **FR-006:** Report schema `reconcile-report/v1` with findings `RC-001`…; categories: stale_as_built, missing_delta, orphan_test, constitution_missing.
- **FR-007:** RECONCILE artifact: `memory-bank/back/reconcile/<epic_id>/reconcile-YYYYMMDD-<slug>.yaml` from new template `.cursor/templates/reconcile/epic-reconcile.yaml`.
- **FR-008:** Appetite: extend `.cursor/templates/plan.md` with section `## Appetite` — fields `timebox_days`, `max_steps`, `cut_list[]`, `circuit_breaker` (text); optional yaml mirror in decompose `index.yaml` top-level `appetite:` block (non-breaking optional keys).
- **FR-009:** RECONCILE workflow FINISH writes reconcile yaml + Handoff; does **not** mutate plan/decompose/code.
- **FR-010:** Unit tests `loop/tests/test_reconcile_spec.py` with fixtures.
- **FR-011:** Document when to use: after BUGFIX, before DECOMPOSE resume, quarterly — in workflow-reconcile.mdc.
- **FR-012:** Exit: default 0 with findings (informational); `--strict` fail on HIGH+.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Stale as_built detected in fixture | pytest | outcome |
| SC-002 | BACK RECONCILE recognized by mainrule | grep mainrule | outcome |
| SC-003 | plan template has Appetite section | file read | outcome |
| SC-004 | Read-only: reconcile run does not change git tracked plan files | pytest tmp git | outcome |

### Assumptions

- Reconcile is advisory in v1 — not wired to stop-gate until opt-in.
- Appetite fields not enforced by loop automatically in v1 — documentation + future hook.

### Clarifications

- Session: 2026-08-30 chat gaps RECONCILE + appetite.
- Not replacement for AUDIT intent↔implement convergence.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL. Soft: whether `--strict` should block loop prepare (defer to v2).

---

## AC

### AC+

1. `BACK RECONCILE` in mainrule index
2. `workflow-reconcile.mdc` + lean gate exist
3. `reconcile-spec` CLI with JSON report
4. Stale as_built fixture test passes
5. plan.md Appetite section added
6. Reconcile artifact template exists
7. Read-only enforced (workflow + test)

### AC−

1. Не мутировать plan/decompose/implement при reconcile
2. Не заменять AUDIT converge
3. Не auto-cut scope in loop from appetite in v1
4. Не scan entire repo — bounded to epic plan_refs/files/as_built/delta paths only
5. Fail-closed: unknown plan-id → exit 2

---

## Техника / архитектура (HOW)

### Layout

| Path | Action |
|------|--------|
| `.claude/hooks/epic/reconcile.py` | Create |
| `.claude/hooks/epic_resolve.py` | Modify — reconcile-spec subcommand |
| `.cursor/rules/back_developer/workflow-reconcile.mdc` | Create |
| `.cursor/rules/back_developer/isolation_rules/_lean/reconcile.mdc` | Create |
| `.cursor/rules/back_developer/mainrule.mdc` | Modify — command row |
| `.cursor/templates/reconcile/epic-reconcile.yaml` | Create |
| `.cursor/templates/plan.md` | Modify — Appetite section |
| `loop/tests/test_reconcile_spec.py` | Create |

### RECONCILE vs ANALYZE vs AUDIT

| Mode | When | Mutates code | Mutates spec |
|------|------|--------------|--------------|
| ANALYZE | pre-IMPLEMENT | no | no |
| RECONCILE | post-hotfix / mid-roadmap | no | no |
| AUDIT | post-epic | no (remediation → IMPLEMENT) | via new sNN only |

### Appetite template (канон)

```markdown
## Appetite

| Field | Value |
|-------|-------|
| timebox_days | 14 |
| max_steps | 12 |
| circuit_breaker | If s05 blocked >2d → cut FR-00X per cut_list |
| cut_list | FR-008 (P1), FR-009 (P1) |
```

### TDD plan

1. Red: stale as_built fixture
2. Red: read-only git check
3. Green: reconcile.py
4. Green: workflow files
5. Green: plan template appetite

---

## Replacement / sunset (brownfield)

n/a — greenfield workflow + CLI.

---

## До DECOMPOSE (черновик нарезки)

| Step | Суть |
|------|------|
| s01 | `reconcile.py` core checks + report schema |
| s02 | `reconcile-spec` CLI |
| s03 | BACK RECONCILE workflow + mainrule + template |
| s04 | plan.md Appetite + optional decompose index appetite keys doc |
| s05 | pytest + read-only guard test |

---

## Следующий режим

→ BACK DECOMPOSE
