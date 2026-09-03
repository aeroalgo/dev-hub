# [T-HUB-026 | spec-reconcile-workflow] PLAN

**Дата:** 2026-08-30  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-spec-maturity-epics.md](roadmap-spec-maturity-epics.md)  
**Queue:** [roadmap-spec-maturity-epics.queue.yaml](roadmap-spec-maturity-epics.queue.yaml)  
**Deps:** нет hard. Soft: T-HUB-024 (parser reuse).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · brainstorming

→ [T-HUB-026-spec-reconcile-workflow/md/decompose-index.md](T-HUB-026-spec-reconcile-workflow/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** лёгкий read-only режим **BACK RECONCILE** + CLI `reconcile-spec` для периодической сверки plan as-built claims ↔ repo reality без full AUDIT; добавить **appetite** fields в plan/decompose schema (timebox, cut_list).
- **gap (as-built):** spec drift после hotfix/вне эпика не ловится до full AUDIT; нет timebox/cut criteria на эпик; RECONCILE mode отсутствует в mainrule router.
- **refs:** `.cursor/rules/mainrule.mdc`; `.cursor/templates/plan.md`; `.cursor/templates/decompose/epic-step.yaml`; T-HUB-012 AUDIT (heavy); chat gap-analysis 2026-08-30.

**CREATIVE need:** нет.

---

## Цель

Оператор запускает **`reconcile-spec` без аргументов** после внеплановой правки — CLI сверяет все **`tasks.md Status=active`** эпики и отдаёт сводный drift report. **Read-only**, без implement yaml mutation. `--plan-id` — отладка; `--strict` — единственный режимный флаг.

---

## Продуктовая speка (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как tech lead, я хочу reconcile report после hotfix, чтобы plan/decompose не врали про as-built. | P0 | Fixture: as_built claims file X → file deleted → RC-001 HIGH |
| US-002 | Как loop-оператор, я хочу `reconcile-spec` без флагов после правки, чтобы не знать заранее epic_id. | P0 | tasks.md active → sweep; queued skipped |
| US-003 | Как loop-оператор, я хочу `BACK RECONCILE` в router, чтобы не гонять full AUDIT для drift check. | P0 | mainrule table includes RECONCILE → workflow file exists |
| US-004 | Как PM, я хочу appetite block в plan (timebox, cut_list), чтобы scope circuit breaker был explicit. | P1 | plan template has Appetite section; decompose index optional mirror |

#### Acceptance Scenarios — US-001

- **Given:** decompose s02 `as_built` lists `src/foo.py`; file removed in repo
- **When:** `reconcile-spec --plan-id T-xxx --cwd $PROJECT_ROOT` (debug)
- **Then:** finding RC-001 severity HIGH; exit 0 (report only) or 1 with `--strict`

#### Acceptance Scenarios — US-002

- **Given:** `tasks.md` Active: T-HUB-023 `Status=active`, T-HUB-024 `Status=queued`
- **When:** `reconcile-spec --cwd $PROJECT_ROOT` (default)
- **Then:** only T-HUB-023 scanned; JSON `mode=active_sweep`

### Functional Requirements (FR-###)

- **FR-001:** New workflow `.cursor/rules/back_developer/workflow-reconcile.mdc` + lean gate `_lean/reconcile.mdc` — STRICTLY READ-ONLY (like ANALYZE).
- **FR-002:** Register `BACK RECONCILE` in `back_developer/mainrule.mdc` command table.
- **FR-003:** CLI `reconcile-spec` in `epic_resolve.py` — `--cwd`; **default (no `--plan-id`)** = sweep `tasks.md` Active rows with `Status=active`; optional `--plan-id` (debug); `--format text|json`; `--strict`. **No** extra scope flags.
- **FR-003a:** Epic selector SoT = `tasks.md` column **Status** = `active` only.
- **FR-004:** Checks: (a) path-like `as_built` exists or in completed implement `deletes`; (b) path-like `delta` if implement `completed`; (c) plan Layout paths; (d) constitution soft LOW.
- **FR-005:** Reuse traceability parsers from T-HUB-024 when merged; duplicate minimal parser OK if 024 not done.
- **FR-006:** Report schema `reconcile-report/v1` with findings `RC-001`…; categories: stale_as_built, missing_delta, missing_plan_path, constitution_missing.
- **FR-007:** RECONCILE artifact: `memory-bank/back/reconcile/<epic_id>/reconcile-YYYYMMDD-<slug>.yaml` from new template `.cursor/templates/reconcile/epic-reconcile.yaml`.
- **FR-008:** Appetite: extend `.cursor/templates/plan.md` with section `## Appetite` — fields `timebox_days`, `max_steps`, `cut_list[]`, `circuit_breaker` (text); optional yaml mirror in decompose `index.yaml` top-level `appetite:` block (non-breaking optional keys).
- **FR-009:** RECONCILE workflow FINISH writes reconcile yaml + Handoff; does **not** mutate plan/decompose/code.
- **FR-010:** Unit tests `loop/tests/test_reconcile_spec.py` (stale as_built, active sweep, unknown plan-id, read-only).
- **FR-011:** Document when to use: **after ad-hoc fix → `reconcile-spec` default**; before DECOMPOSE resume; quarterly — in workflow-reconcile.mdc.
- **FR-012:** Exit: default 0 with findings; `--strict` fail on HIGH+; unknown `--plan-id` → exit 2; empty active → exit 0.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Stale as_built detected in fixture | pytest | outcome |
| SC-002 | Default sweep uses tasks.md active only | pytest active_sweep | outcome |
| SC-003 | BACK RECONCILE recognized by mainrule | grep mainrule | outcome |
| SC-004 | plan template has Appetite section | file read | outcome |
| SC-005 | Read-only: reconcile run does not change git tracked plan files | pytest tmp git | outcome |

### Assumptions

- Reconcile is advisory in v1 — not wired to stop-gate until opt-in.
- Appetite fields not enforced by loop automatically in v1 — documentation + future hook.

### Clarifications

- Session: 2026-08-30 chat gaps RECONCILE + appetite.
- Session: 2026-08-31 — default `reconcile-spec` = sweep **`tasks.md Status=active`** (no epic_id required after ad-hoc fix); `--plan-id` debug-only; no multi-flag scope selectors.
- Not replacement for AUDIT intent↔implement convergence.
- «Правка вне эпика» = код меняли не через IMPLEMENT shards **существующего** epic, не «нет plan вообще».

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL. Soft: whether `--strict` should block loop prepare (defer to v2).

---

## AC

### AC+

1. `BACK RECONCILE` in mainrule index
2. `workflow-reconcile.mdc` + lean gate exist
3. `reconcile-spec` CLI: default active sweep + optional `--plan-id`
4. Stale as_built + active sweep fixture tests pass
5. plan.md Appetite section added
6. Reconcile artifact template exists
7. Read-only enforced (workflow + test)

### AC−

1. Не мутировать plan/decompose/implement при reconcile
2. Не заменять AUDIT converge
3. Не auto-cut scope in loop from appetite in v1
4. Не scan entire repo — bounded to selected epic plan/decompose/implement paths only
5. Fail-closed: unknown `--plan-id` → exit 2
6. Не требовать от оператора знать epic_id после hotfix — default sweep по active

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

### Default CLI (канон)

```bash
# после внеплановой правки — без аргументов
.epic_resolve reconcile-spec --cwd "$PROJECT_ROOT"

# отладка одного эпика
.epic_resolve reconcile-spec --cwd "$PROJECT_ROOT" --plan-id T-HUB-023

# CI / строгий gate
.epic_resolve reconcile-spec --cwd "$PROJECT_ROOT" --strict
```

Selector: parse `memory-bank/tasks.md` → section `## Active` → rows where column **Status** = `active` (case-insensitive). Resolve `decompose-{epic_id}*/index.yaml` per row.

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
| s01 | `reconcile.py` core checks + report schema + `list_active_epic_ids` |
| s02 | `reconcile-spec` CLI (default active sweep, optional `--plan-id`) |
| s03 | BACK RECONCILE workflow + mainrule + template |
| s04 | plan.md Appetite + optional decompose index appetite keys doc |
| s05 | pytest + read-only guard test |

---

## Следующий режим

→ BACK DECOMPOSE
