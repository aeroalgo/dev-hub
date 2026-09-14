# [T-HUB-101-incident-clear-on-start-removal] PLAN

**Дата:** 2026-09-14  
**Режим:** BACK PLAN (REPLAN spawn)  
**Уровень:** L2  
**Статус:** active  
**iteration:** 2  
**Replan-of:** `T-HUB-079-orchestrator-lifecycle-reliability`  
**Parent-prompt:** [memory-bank/back/plan/T-HUB-079-orchestrator-lifecycle-reliability/md/prompt.md](../../T-HUB-079-orchestrator-lifecycle-reliability/md/prompt.md) — immutable prior Epic SoT  
**Parent-replan:** [memory-bank/back/plan/T-HUB-079-orchestrator-lifecycle-reliability/md/replan-i2.yaml](../../T-HUB-079-orchestrator-lifecycle-reliability/md/replan-i2.yaml)  
**Parent I1 QA:** [memory-bank/back/qa/T-HUB-079-orchestrator-lifecycle-reliability/qa-20260910-lifecycle-reliability-v7.yaml](../../../qa/T-HUB-079-orchestrator-lifecycle-reliability/qa-20260910-lifecycle-reliability-v7.yaml)  
**Prompt (this epic):** [md/prompt.md](prompt.md)  
**Deps:** hard `T-HUB-079` (parent I1 in done; outcome continuity via Parent-prompt)  
**Batch:** replan-spawn-075-080-20260914  

→ После DECOMPOSE единственный трекер — `yaml/decompose-index.yaml`.

## Provenance

- Spawned by REPLAN of `T-HUB-079-orchestrator-lifecycle-reliability` on 2026-09-14.
- Prior Epic outcome SoT: `memory-bank/back/plan/T-HUB-079-orchestrator-lifecycle-reliability/md/prompt.md` (do not rewrite parent prompt).
- Parent remains in roadmap `done:`; this epic is the sole I2 delivery vehicle.
- I1 plan/decompose/QA under parent are historical; not overwritten.

## Outcome summary

I1 закрыл idempotent dispatch, terminal telemetry, typed parent API и purge marker-based repair. Остаётся один критический legacy-путь: при каждом старте outer loop orchestrator автоматически вызывает `IncidentTracker.clear_open_on_start` → `resolve_all_open_incidents` с `resolution_action: clear_open_on_loop_start`, стирая все open incidents до того, как оператор или audit увидят typed failure surface.

Это прямо нарушает prompt **Forbidden after:** «Marker clearing» и ослабляет **Done when #2:** «An interrupted or empty session is visible as a terminal event with cause» — open incidents с diagnostic codes исчезают при рестарте loop, а не остаются forensic state до явного operator recovery.

I2 закрывает только этот gap: убрать автоматический clear на start, сохранить opt-in operator boundary (`incident-clear-open`), fail-closed visibility open incidents.

## Gap classification

| ID | Класс | Описание | Поверхность |
|---|---|---|---|
| G079-I2-01 | `legacy_removal` | `IncidentTracker.clear_open_on_start` (~49–68) и вызов из `Orchestrator.run()` (~286) автоматически резолвят все open incidents при старте loop с `resolution_action: clear_open_on_loop_start`. Запрещено после prompt; стирает actionable typed failure surface. | `loop/runner/orchestrator.py`, `loop/incidents/store.py` (consumer only), тесты orchestrator |

**Не входит в I2 (backlog / чужие эпики):** capability evidence write-deny (077), TestFingerprintCache (078), agents instruction corpus (080), managed `capability_checks` (076).

## backlog_candidates

- **LifecycleReducer in-memory `_by_key` durability** при process crash — только если telemetry уже показывает terminal-by-cause без auto-clear; полный durable reducer rewrite не входит в I2, если gap #1 закрывается без него.
- **Provider dashboard / UI** — визуализация lifecycle/incidents вне scope prompt.

## Technology axiom

| Выбор | Machine boundary | FORBIDDEN после I2 |
|---|---|---|
| Open incident persistence | JSONL `incidents.jsonl` + typed `IncidentRecord` | Автоматический resolve всех open records на loop start |
| Operator recovery | CLI `incident-clear-open` (opt-in, audited `resolution_action`) | Implicit marker/incident clearing как нормальное поведение agent/loop |
| Orchestrator start | Lease acquire + prep/resync без side-effect на incidents | `clear_open_on_start` или эквивалентный bulk resolve |
| Fail-closed visibility | Open incidents остаются `status: open` до explicit operator command | Silent wipe + stdout «cleared N incidents» без opt-in |

## User Stories и Independent Test

| # | Story | Priority | Independent Test |
|---|---|---|---|
| US-I2-001 | Как оператор loop, я хочу видеть open incidents после рестарта процесса, чтобы forensic typed failure surface не исчезала до явного решения. | P0 | Start orchestrator twice with pre-seeded open incident → после второго start incident остаётся open; auto-resolve не вызывается. |
| US-I2-002 | Как оператор, я хочу явно очистить stale open incidents через CLI, когда recovery осознанный и audited. | P0 | `incident-clear-open --json` resolves open records с documented `resolution_action`; orchestrator start без этого CLI не меняет incidents. |

### Acceptance Scenarios — US-I2-001

- **Given:** в `incidents.jsonl` есть open incident с diagnostic codes после terminal failure предыдущей сессии.
- **When:** outer loop orchestrator выполняет `run()` (новый process start).
- **Then:** incident остаётся `open`; `cleared_count == 0`; stdout не содержит auto-clear сообщения; forensic state доступен через list/open API и JSONL.

- **Given:** orchestrator стартует на чистом epic_dir без incidents.
- **When:** `run()` выполняется.
- **Then:** no-op без ошибок; bulk resolve не вызывается.

### Acceptance Scenarios — US-I2-002

- **Given:** несколько open incidents в epic_dir.
- **When:** оператор выполняет `python -m loop.context_loop incident-clear-open --json` (или эквивалент documented CLI).
- **Then:** все open incidents resolved с явным `resolution_action`; JSON output содержит `cleared_count`, `incident_ids`, `diagnostic_codes`; это единственный supported bulk-clear path.

- **Given:** operator не вызывал `incident-clear-open`.
- **When:** loop перезапускается N раз.
- **Then:** open incidents persist; ни один restart не подменяет operator decision.

## Functional Requirements (FR)

- **FR-I2-001:** `Orchestrator.run()` MUST NOT вызывать bulk resolve open incidents на startup; блок ~285–294 с `clear_open_on_start` удаляется или заменяется no-op без side-effect на `incidents.jsonl`.
- **FR-I2-002:** `IncidentTracker.clear_open_on_start` MUST быть удалён или превращён в deprecated stub, который fail-closed raise/логирует при вызове; единственный machine path bulk-clear — operator CLI.
- **FR-I2-003:** Open incidents MUST оставаться visible (`status: open`) across process restart до explicit `incident-clear-open` или per-incident resolve API; forensic diagnostic codes не теряются.
- **FR-I2-004:** CLI `incident-clear-open` MUST оставаться единственным opt-in audited bulk recovery; `resolution_action` и `resolution_tier` фиксируются в resolved record (не silent delete).
- **FR-I2-005:** Тесты `loop/tests/test_runner_orchestrator.py` MUST быть обновлены: убрать expectations на `clear_open_on_start.assert_called_once`; добавить regression — restart не clears incidents.
- **FR-I2-006:** Тесты incidents CLI/store MUST подтверждать, что auto-start path отсутствует; существующий `test_resolve_all_open_incidents` остаётся valid для operator CLI path only.
- **FR-I2-007:** Kind I surfaces MUST NOT instruct agent/loop to auto-clear incidents or markers on restart; если такие фразы есть — rewrite на operator-only recovery (без расширения scope за пределы incident clearing).

## NFR

- **NFR-I2-001:** Изменение не добавляет новый persistence layer и не требует migration существующих resolved records.
- **NFR-I2-002:** Startup orchestrator не выполняет write I/O на `incidents.jsonl` кроме уже существующих trace/telemetry paths вне scope этого gap.
- **NFR-I2-003:** Operator CLI contract (`incident-clear-open`, JSON output) остаётся backward-compatible; breaking change запрещён без documented migration.
- **NFR-I2-004:** I2 не меняет idempotency keys, reducer transitions, receipt provenance (077) или capability evidence paths.

## Target layout

| Surface / owner | Paths | I2 responsibility |
|---|---|---|
| Orchestrator startup | `loop/runner/orchestrator.py` | Удалить auto `clear_open_on_start` call в `run()`; убрать/deprecate `IncidentTracker.clear_open_on_start`. |
| Incident bulk resolve (operator) | `loop/context_loop.py` (`incident-clear-open`), `loop/incidents/store.py::resolve_all_open_incidents` | Сохранить как единственный opt-in bulk path; default `resolution_action` для CLI остаётся explicit operator action (не `clear_open_on_loop_start` на auto-start). |
| Tests — orchestrator | `loop/tests/test_runner_orchestrator.py` | Убрать mock expectations auto-clear; добавить regression open-incident survives restart. |
| Tests — incidents | `loop/tests/test_incidents_cli.py`, `loop/tests/test_incidents_schema_store.py` | Подтвердить CLI path; не conflate с orchestrator start. |
| Kind I (if any) | `loop/WORKFLOW.md`, operator docs referencing auto-clear on start | Rewrite: explicit operator recovery only. |

**Wire-complete ladder I2:** remove auto-call → wire operator-only path → enforce (tests deny auto-clear) → purge `clear_open_on_start` symbol and Kind I phrases.

## Sunset A / B / C / I (Kind I)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
|---|---|---|
| `IncidentTracker.clear_open_on_start` | удаление; operator CLI `incident-clear-open` | delete in-epic |
| `Orchestrator.run()` блок auto-clear (~285–294) | no startup incident mutation | delete in-epic |
| `resolution_action: clear_open_on_loop_start` как автоматический default на loop start | только explicit operator invocation с audited action | delete in-epic |
| Mock/test branches expecting `clear_open_on_start` on every run | regression tests: incidents survive restart | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| Implicit «loop restart clears incidents» behavior | Documented `incident-clear-open` operator step | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена (fail-closed) | Policy |
|---|---|---|
| `except Exception: return ok/cleared_count 0` в auto-clear swallowing errors | Fail-closed: no auto path; operator CLI surfaces errors | delete in-epic |
| Treating restart as implicit incident hygiene | Open incidents remain until operator acts | delete in-epic |

### I. Instruction surfaces (Kind I)

| Устаревает (phrase / path) | Замена | Policy |
|---|---|---|
| Любая инструкция «open incidents cleared on loop start» / «restart resets incident state» | «Open incidents persist; use `incident-clear-open` for explicit operator recovery» | delete in-epic |
| Agent/runtime advice to clear markers/incidents on restart as normal behavior | Operator-only, fail-closed handoff per prompt Forbidden after | delete in-epic |

## AC

1. Orchestrator `run()` на startup не вызывает bulk resolve open incidents; pre-seeded open incident остаётся open после restart.
2. `IncidentTracker.clear_open_on_start` удалён или unreachable; grep по repo не находит live call path from orchestrator start.
3. `incident-clear-open` CLI остаётся рабочим opt-in bulk recovery с JSON output и audited resolution fields.
4. Regression tests orchestrator не expect `clear_open_on_start`; новый test подтверждает forensic persistence.
5. Prompt **Forbidden after** «Marker clearing» не нарушается автоматическим wipe на start.

### AC−

1. Нет автоматического resolve open incidents при loop/process start.
2. Нет dual path: auto-clear + operator CLI как равноправные bulk recovery.
3. Нет silent swallow ошибок incident store на startup через auto-clear try/except.
4. Нет расширения scope на durable reducer rewrite, dashboard, 077/078/080/076.
5. Нет instruction surface, обучающей agent auto-clear incidents/markers on restart.

## QA consumes (#qa-consumes)

| ID | Priority | Scenario | Command / fixture | Expected | Maps |
|---|---|---|---|---|---|
| TM-079-I2-01 | P0 | Open incident survives orchestrator restart | `bin/pytest loop/tests/test_runner_orchestrator.py -q --tb=line -k 'incident or clear_open'` | Pre-seeded open incident remains open; no `clear_open_on_start` call | FR-I2-001,003; AC-1 |
| TM-079-I2-02 | P0 | No live auto-clear symbol path | `rg 'clear_open_on_start' loop/` + targeted pytest | Zero call sites from orchestrator; symbol removed or dead | FR-I2-002; AC-2 |
| TM-079-I2-03 | P0 | Operator CLI bulk clear works | `bin/pytest loop/tests/test_incidents_cli.py -q --tb=line -k clear_open` | CLI resolves with explicit action; not triggered by orchestrator start | FR-I2-004; AC-3 |
| TM-079-I2-04 | P1 | Full hub regression | `bin/pytest -q --tb=line` | Suite green; I1 lifecycle behavior intact | NFR-I2-004 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| Prompt Epic alignment | I2 scope ⊆ Epic outcome + Forbidden after | done | Single legacy_removal gap mapped to marker clearing prohibition |
| Gap-only scope | No outcome expansion | done | backlog_candidates excluded; foreign epics listed as out-of-scope |
| Technology axiom | Replace-not-wrap | done | Auto-clear deleted; operator CLI sole bulk path |
| qa_consumes | ≥3 TM | done | TM-079-I2-01…04 |
| Delivery closure | P0 boundary defined | done | See below |

## Delivery closure

| Capability / outcome | Classification | Production entrypoint | Enforcement | Independent test | Follow-up |
|---|---|---|---|---|---|
| Fail-closed incident visibility on restart | `legacy_removal` | `Orchestrator.run()` without incident mutation | Tests deny auto-clear; open records persist | TM-079-I2-01 | n/a |
| Operator-only bulk incident recovery | `hardening` (minimal) | `incident-clear-open` CLI | Existing CLI tests + no orchestrator alias | TM-079-I2-03 | n/a |

## Appetite

| Поле | Значение |
|---|---|
| `timebox_days` | `1` |
| `cut_list` | `['LifecycleReducer durable _by_key rewrite', 'provider dashboard/UI', '077 evidence write-deny', '078 fingerprint cache', '080 agents corpus', '076 capability_checks']` |

## Следующий режим

→ **BACK DECOMPOSE T-HUB-101-incident-clear-on-start-removal** (iteration 2)
