# [T-HUB-024 | validate-traceability] PLAN

**Дата:** 2026-08-30  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-spec-maturity-epics.md](roadmap-spec-maturity-epics.md)  
**Queue:** [roadmap-spec-maturity-epics.queue.yaml](roadmap-spec-maturity-epics.queue.yaml)  
**Deps:** нет hard. Soft: T-HUB-011 ANALYZE (semantic overlap).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · modern-python

→ [decompose-T-HUB-024-validate-traceability/index.md](decompose-T-HUB-024-validate-traceability/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** machine-enforced traceability: каждый FR/SC/US из plan имеет покрытие в decompose `plan_refs`, каждый sNN ссылается на plan requirement или `out_of_scope` в plan; completed implement shard имеет tests/files evidence; optional living acceptance через `@pytest.mark.ac`.
- **gap (as-built):** `validate-step` проверяет формат одного shard; ANALYZE — read-only human/AI pass без CI exit code; product epics (T-060) вручную мапят FR→tests; drift guard только в одном shard (s10 registry).
- **refs:** `.claude/hooks/epic_resolve.py`; `.claude/hooks/epic/core.py`; `loop/YAML-CONTRACT.md`; `.cursor/rules/shared/workflow-analyze-core.mdc` pass 3–4; chat gap-analysis 2026-08-30.

**CREATIVE need:** нет.

---

## Цель

Один CLI-команда и pytest suite доказывают, что эпик **traceable end-to-end** (plan requirements ↔ decompose ↔ implement evidence ↔ optional ac-markers) — fail-closed, без silent skip.

---

## Продуктовая спека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как loop-оператор, я хочу `validate-traceability` перед DECOMPOSE merge, чтобы FR без sNN не попали в IMPLEMENT. | P0 | Fixture plan+decompose с missing FR → exit 1 + finding ID |
| US-002 | Как parent-агент, я хочу видеть matrix FR→sNN→test в stdout/JSON, чтобы закрыть gaps до `@verify`. | P0 | `--format json` на T-HUB-021 fixture → covered/missing arrays |
| US-003 | Как QA продукта, я хочу opt-in `@pytest.mark.ac("US-001-AS1")` registry, чтобы acceptance scenarios были searchable. | P1 | pytest collect-only finds ac markers; validate warns on orphan ac |

#### Acceptance Scenarios — US-001

- **Given:** plan с FR-001, FR-002; decompose s01 covers только FR-001; FR-002 в plan без out_of_scope
- **When:** `epic_resolve.py validate-traceability --plan-id T-xxx --cwd $PROJECT_ROOT`
- **Then:** exit 1; finding `TR-001` missing requirement coverage FR-002

#### Acceptance Scenarios — US-002

- **Given:** completed implement s01 with tests/files populated
- **When:** validate after IMPLEMENT
- **Then:** matrix row FR-001 → s01 → `loop/tests/test_*.py` path

### Functional Requirements (FR-###)

- **FR-001:** Новый subcommand `validate-traceability` в `epic_resolve.py` с `--cwd`, `--plan-id`, optional `--format text|json`, `--strict`.
- **FR-002:** Parser plan: extract FR-###, SC-###, US-### из `memory-bank/back/plan/plan-<id>.md` (regex + table rows); ignore `[НУЖНО УТОЧНИТЬ]` block for coverage (warn only).
- **FR-003:** Parser decompose: load all `decompose-<id>/s*.yaml`; collect `plan_refs`, `goal`, `out_of_scope`; build FR→sNN map.
- **FR-004:** Coverage rule: каждый FR/SC P0/P1 из plan → ≥1 sNN `plan_refs` OR explicit `out_of_scope` entry in plan §Нецели/Assumptions with requirement ID.
- **FR-005:** Reverse rule: каждый sNN must have non-empty `plan_refs` OR documented in plan draft outline as exploratory (warn MEDIUM, not CRITICAL for sNN-audit-*).
- **FR-006:** Implement evidence: for sNN with `status: completed` in implement yaml — require non-empty `tests` or `files` with test path pattern.
- **FR-007:** Optional ac registry: scan `tests/**/*.py` for `@pytest.mark.ac("...")`; cross-check against plan Acceptance Scenarios ids if `--ac-strict`.
- **FR-008:** Findings schema stable IDs `TR-001`… deterministic order; severity CRITICAL/HIGH/MEDIUM/LOW aligned with ANALYZE heuristic.
- **FR-009:** Exit 0 only when CRITICAL=0; `--strict` elevates HIGH to fail.
- **FR-010:** Unit tests in `loop/tests/test_validate_traceability.py` with fixture mini plan/decompose trees under `loop/tests/fixtures/traceability/`.
- **FR-011:** Document in `loop/YAML-CONTRACT.md` + workflow DECOMPOSE FINISH tip: run validate before index complete.
- **FR-012:** Opt-in loop hook: `EPIC_TRACEABILITY_CHECK=1` in prepare prompt when decompose index all steps `pending`→first IMPLEMENT (soft warn in prompt, not block until green suite).

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Fixture missing-FR detected 100% | pytest | outcome |
| SC-002 | Hub loop/tests green with new command | `pytest loop/tests/ -q` | outcome |
| SC-003 | T-HUB-021 decompose validates with CRITICAL=0 post-IMPLEMENT | manual/CI on hub epic | outcome |
| SC-004 | JSON output schema versioned `traceability-report/v1` | pytest snapshot | outcome |

### Assumptions

- Plan IDs follow `FR-###` / `SC-###` / `US-###` convention (already in template).
- Decompose shards use `plan_refs: ["plan-T-xxx FR-001"]` or similar strings (existing T-060 pattern).
- Products run epic_resolve from dev-hub with `--cwd $PROJECT_ROOT`.

### Clarifications

- Session: 2026-08-30 chat — gap «executable spec / validate-traceability».
- Scope: hub tooling + workflow refs; product inventory (T-058) out of scope — products opt-in ac markers locally.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL. Soft: exact regex for plan table parsing at IMPLEMENT (markdown edge cases).

---

## AC

### AC+

1. `validate-traceability --help` documents all flags
2. Missing FR coverage → exit 1 with `TR-*` finding
3. Completed implement without tests → HIGH finding
4. JSON report includes `coverage_pct`, `critical_count`, `matrix[]`
5. Fixture-based unit tests ≥12 cases (missing FR, orphan sNN, happy path, ac orphan)
6. `loop/YAML-CONTRACT.md` updated
7. No network; no product repo mutation

### AC−

1. Не заменять ANALYZE workflow — complement only
2. Не блокировать `finalize-step` автоматически в v1 (opt-in `--strict` / env only)
3. Не парсить полный plan markdown AST — bounded regex OK with tests
4. Не require ac markers by default
5. Fail-closed: missing plan or decompose dir → exit 2 with clear error (not exit 0)

---

## Техника / архитектура (HOW)

### Стек

- Python 3.11+ (hub `.venv`)
- Existing: `epic_yaml.py`, yaml load from `epic/core.py`
- New module: `.claude/hooks/epic/traceability.py`

### Layout

| Path | Action |
|------|--------|
| `.claude/hooks/epic/traceability.py` | Create — parsers, matrix, report |
| `.claude/hooks/epic_resolve.py` | Modify — subcommand wiring |
| `loop/tests/fixtures/traceability/` | Create — mini plan/decompose sets |
| `loop/tests/test_validate_traceability.py` | Create |
| `loop/YAML-CONTRACT.md` | Modify |
| `.cursor/rules/back_developer/workflow-decompose.mdc` | Modify — FINISH tip one paragraph |

### Report shape (канон)

```yaml
schema: traceability-report/v1
plan_id: T-HUB-024
metrics:
  coverage_pct: 92.0
  critical_count: 0
  high_count: 1
findings:
  - id: TR-001
    severity: CRITICAL
    category: coverage_gap
    requirement: FR-007
    message: "No sNN plan_refs"
matrix:
  - requirement: FR-001
    steps: [s01, s02]
    tests: [loop/tests/test_validate_traceability.py]
```

### TDD plan

1. Red: fixture missing FR → expect TR-001
2. Red: happy epic fixture → exit 0
3. Red: JSON schema fields
4. Green: traceability.py
5. Green: epic_resolve subcommand
6. Refactor: share requirement regex with analyze if trivial

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield |

---

## До DECOMPOSE (черновик нарезки)

| Step | Суть |
|------|------|
| s01 | `traceability.py` parsers + report schema + unit fixtures |
| s02 | `epic_resolve validate-traceability` CLI + exit codes |
| s03 | ac marker scanner + optional `--ac-strict` |
| s04 | YAML-CONTRACT + workflow decompose tip |
| s05 | loop prompt opt-in `EPIC_TRACEABILITY_CHECK` + integration test on hub epic fixture |

---

## Следующий режим

→ BACK DECOMPOSE
