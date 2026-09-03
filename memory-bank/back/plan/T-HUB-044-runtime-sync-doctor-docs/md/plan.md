# [T-HUB-044 | runtime-sync-doctor-docs] PLAN

**Дата:** 2026-09-01  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-universal-runtime-epics.md](roadmap-harness-universal-runtime-epics.md)  
**Queue:** [roadmap-harness-universal-runtime-epics.queue.yaml](roadmap-harness-universal-runtime-epics.queue.yaml)  
**Deps:** **hard** T-HUB-043. **Soft:** T-HUB-030 (doctor CLI patterns), T-HUB-009 (DSH runbook style).

**Skills:** writing-plans · python-testing-patterns

→ [T-HUB-044-runtime-sync-doctor-docs/md/decompose-index.md](T-HUB-044-runtime-sync-doctor-docs/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** После harness extract + runtime adapters operators need docs, doctor preflight, hub-link updates, board launch `--runtime codex` parity — без этого universal runtime не adoptable.
- **deps:** **hard** T-HUB-043 (shipped surfaces). **Soft:** T-HUB-030 doctor subcommand patterns.
- **refs:** `README.md`, `loop/WORKFLOW.md`, `docs/runbooks/dsh-loop-pilot.md`, `bin/hub-link`, `loop/board_sync/cli.py`, `loop/board_launch/loop_argv.py`.

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| README | таблица runtimes: claude (default), dsh, codex; loop support matrix updated |
| Runbook | `docs/runbooks/codex-loop-pilot.md` mirrors dsh pilot structure |
| Doctor | `context_loop doctor` (or extend existing) checks: registry, runtime-sync --check, binary presence |
| hub-link | document harness path; optional link `.codex` generated dir note |
| board launch | `--runtime` choices from registry (codex added) |
| AGENTS.md stub | mention harness/ + EPIC_RUNTIME values |

**CREATIVE need:** нет.

---

## Продуктовая spека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator, я хочу runbook codex loop, чтобы запустить EPIC_RUNTIME=codex без чата. | P0 | runbook steps exist + doctor passes |
| US-002 | Как operator, я хочу doctor preflight, чтобы видеть drift/missing binary до loop. | P0 | doctor --json reports codex status |
| US-003 | Как reader README, я хочу актуальную runtime matrix. | P0 | README lists codex loop ✅ |
| US-004 | Как board user, я хочу arm loop with --runtime codex. | P1 | board CLI accepts codex |

### Functional Requirements

- **FR-001:** Update `README.md` §Supported agents — codex loop headless ✅; prerequisites (codex login, runtime-sync).
- **FR-002:** Update `loop/WORKFLOW.md` — runtime registry reference, harness/ pointer.
- **FR-003:** Create `docs/runbooks/codex-loop-pilot.md` — install, auth, sync, EPIC_RUNTIME=codex, troubleshooting.
- **FR-004:** Create `harness/README.md` — layer explanation (if not done in 041).
- **FR-005:** Extend doctor: `runtime_registry_ok`, `runtime_sync_ok`, `runtime_binary_ok(codex|dsh|claude)`.
- **FR-006:** `loop/board_sync/cli.py` + `loop/board_launch/loop_argv.py` — runtime choices from registry.
- **FR-007:** Update `bin/hub-link` AGENTS.md stub text for harness + codex.
- **FR-008:** `memory-bank/architecture/services.md` — S-HUB-RUNTIME-SYNC service row.
- **FR-009:** pytest: doctor runtime checks with mocks.

---

## AC+

1. README runtime table includes codex loop (headless) with link to runbook.
2. `docs/runbooks/codex-loop-pilot.md` exists with install + EPIC_RUNTIME=codex + runtime-sync steps.
3. `python3 loop/context_loop.py doctor --json` includes runtime sync/registry diagnostics.
4. board `--runtime codex` accepted (test_board_launch_cli or argv test).
5. `loop/tests/test_doctor_runtime.py` green.

### AC−

1. Stale README "loop не запускает Codex".
2. Doctor silent pass when runtime-sync drift on EPIC_RUNTIME=codex.

---

## Техника / архитектура (HOW)

### Doctor checks (draft)

| Check ID | Condition | Severity |
|----------|-----------|----------|
| runtime_registry_valid | registry yaml loads | error |
| runtime_sync_drift | `--check` non-zero | warn (v1) / error (optional flag) |
| runtime_binary_codex | codex in PATH when EPIC_RUNTIME=codex | error |

### Files

| Файл | Действие |
|------|----------|
| `README.md` | update |
| `loop/WORKFLOW.md` | update |
| `docs/runbooks/codex-loop-pilot.md` | new |
| `codex/README.md` | extend (from 043) |
| `loop/context_loop.py` | doctor runtime section |
| `loop/board_sync/cli.py` | dynamic runtime choices |
| `loop/board_launch/loop_argv.py` | codex env_extra |
| `bin/hub-link` | AGENTS stub |
| `memory-bank/architecture/services.md` | row |
| `loop/tests/test_doctor_runtime.py` | new |

---

## Eng review spine

### Data flow

```text
[operator] -> [doctor] -> [registry load + runtime-sync --check + which-codex]
          -> [make loop EPIC_RUNTIME=codex] -> [runbook preflight OK]
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| doctor | missing registry | doctor json | error field | TM-001 |
| docs | broken links | markdown review | fix | TM-002 |
| board CLI | codex rejected | pytest | fix argv | TM-003 |

---

## Replacement / sunset

### A. Code

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| README codex loop ❌ row | ✅ + runbook link | update in-epic |
| hardcoded board runtime choices | registry-driven | delete in-epic |

---

<a id="qa-consumes"></a>
## QA consumes

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | doctor runtime json | pytest loop/tests/test_doctor_runtime.py | PASS | FR-005 |
| TM-002 | P0 | board codex runtime | pytest loop/tests/test_board_launch_cli.py -k codex | PASS | FR-006 |
| TM-003 | P1 | runbook exists | test file path fixture | file exists | FR-003 |
| TM-004 | P1 | README not stale | grep README no "не запускает Codex" | 0 matches | AC-1 |

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| Product probe | L2 lite | done | user stories |
| Eng spine | L2+ | done | failure matrix |
| qa_consumes | L2+ | done | 4 TM |

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | README + WORKFLOW updates |
| s02 | codex-loop-pilot runbook |
| s03 | doctor runtime checks |
| s04 | board launch registry runtime |
| s05 | hub-link AGENTS stub + architecture row |
| s06 | tests + doc link audit |

---

## Appetite

| Поле | Значение |
| :--- | :--- |
| `timebox_days` | 3 |
| `cut_list` | `['board codex UI filter', 'doctor hard fail on sync drift']` |

---

## Следующий режим

→ BACK DECOMPOSE (after T-HUB-043)
