# Реестр шагов (Decompose index) — T-HUB-015

**Plan ID:** T-HUB-015-dsh-board-arm-loop
**План:** [plan/T-HUB-015-dsh-board-arm-loop/md/plan.md](../plan/T-HUB-015-dsh-board-arm-loop/md/plan.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-08-29
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

---

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `brainstorming` | batch-решения уже закрыты в PLAN |

**Per-step:** BACK — skills gate в каждом `sNN` (см. `workflow-decompose.mdc`).

---

## Requirements coverage (plan → steps)

### AC+ (план §AC → sNN)

| AC+ | Описание | sNN | Покрытие |
| :--- | :--- | :--- | :--- |
| AC+1 | Unit: `parse_card_metadata` valid/invalid | s02 | cp1: valid round-trip; cp2: invalid → ValueError |
| AC+2 | Unit: `build_arm_argv` / `build_loop_argv` exact lists | s03 | cp1: argv exact match preset; cp2: env-wins path |
| AC+3 | Unit: arm_from_card happy path updates fixture activeContext | s04 | cp2: fixture activeContext after arm |
| AC+4 | Unit: step_mismatch fails | s04 | cp3: exit 2 + diagnostic_code |
| AC+5 | Unit: arm-loop short-circuits on arm failure (loop not called) | s06 | cp2: loop not invoked on arm fail |
| AC+6 | Unit/Fake: loop stub exit 0 → execution succeeded | s05 | cp1: fake subprocess succeeded |
| AC+7 | Plugin/config: mb run intercepted (or alternate UI path documented + tested) | s08 | cp1/cp2: intercept or deny path |
| AC+8 | Non-mb run passthrough | s08 | cp3: non-mb cards unchanged |
| AC+9 | Docs runbook in `dsh/README.md` | s10 | cp1: runbook sections exist |
| AC+10 | `hub-board arm\|loop\|arm-loop --help` | s07 | cp1: all subcommands parse |
| AC+11 | Unit: workspace filter logic (metadata.workspace_id) | s09 | cp1: filter hides wrong ws |
| AC+12 | Unit: model preset whitelist validation rejects bad tokens | s03 | cp3: bad token rejected |
| AC+13 | Plugin: header controls render; Sync calls hub-board | s09 | cp2: render + sync invoked |
| AC+14 | Docs: model precedence table + workspace filter + runtime toggle | s10 | cp2: README sections exist |

### AC− (план §AC− → sNN)

| AC− | Описание | sNN | Enforcement |
| :--- | :--- | :--- | :--- |
| AC−1 | Не делать board SoT | s04, s05 | arm writes only activeContext/epic state; no ledger write |
| AC−2 | Не вызывать произвольный shell из browser payload | s08 | plugin spawns fixed argv via python-bridge; no raw shell |
| AC−3 | Не `roadmap-advance` с доски по умолчанию | s04 | `allowRoadmapAdvance=false`; gate arm does not call roadmap-advance |
| AC−4 | Не требовать Jira | — | out_of_scope plan; no sNN needed |
| AC−5 | Не заменять `finalize-step` / verify gates | s05, s06 | loop subprocess runs full pipeline; bridge doesn't bypass |
| AC−6 | Не запускать frontend tests из plugin | s09 | TypeScript/Cordis plugin — no Python test runner invocation |
| AC−7 | Не silent fallback stock agent run for mb-cards | s08 | intercept → explicit error `mb_card_requires_loop_run` |
| AC−8 | Не использовать stock `task.mode` как model path для mb-* loop | s03, s08 | build_loop_argv ignores task.mode; bridge enforces |
| AC−9 | Не allow free-text model input from browser (whitelist only) | s03, s09 | preset id validated against whitelist; UI exposes only preset dropdown |
| AC−10 | Не mutate ledger при workspace filter (view-only) | s09 | filter is DOM-only; no API write |

### FR покрытие

| FR | Описание | sNN |
| :--- | :--- | :--- |
| FR-001 | Parse `mb-board-card/v1`; invalid → fail-closed | s02 |
| FR-001b | `card_kind=gate` → gate arm; `card_kind=step` → step rules | s02, s04 |
| FR-002 | `arm_from_card` → `context_loop.arm`; step_id verify | s04 |
| FR-003 | `loop_from_card` → spawn `DEV_HUB/bin/loop`; capture exit | s05 |
| FR-004 | `arm_loop_from_card` = arm then loop; stop if arm fails | s06 |
| FR-005 | Cordis plugin `@dev-hub/dsh-mb-bridge`; intercept + redirect | s08 |
| FR-006 | CLI `hub-board arm\|loop\|arm-loop` + flags | s07 |
| FR-007 | Execution recording: board executions update | s05 |
| FR-008 | Config schema (devHub, loopBin, modelPresets, etc.) | s08 (config load); s03 (preset validation) |
| FR-009 | Docs runbook in dsh/README.md | s10 |
| FR-010 | Tests: arm matching, argv, plugin, filter, preset | s02–s07, s09, s10 |
| FR-011 | Auto `hub-board sync` when syncAfterLoop=true | s06 |
| FR-012 | Workspace filter dropdown; client-side; localStorage | s09 |
| FR-013 | Sync button → `hub-board sync --workspace-id` | s09 |
| FR-014 | Model preset whitelist; max 8 entries; token validation | s03 |
| FR-015 | `build_loop_argv` precedence: env > preset > defaultLoopArgs > bare | s03 |
| FR-016 | Runtime toggle: config + UI; `EPIC_RUNTIME` env on subprocess | s03, s09 |
| FR-017 | Card detail: Arm+Run primary; Arm/Run secondary; stock Run hidden | s08 |
| FR-018 | FORBIDDEN: raw shell, arbitrary model, stock task.mode for mb-* | s03, s08, s09 |

### NFR покрытие

| NFR | Описание | sNN |
| :--- | :--- | :--- |
| NFR: fail-closed | parse invalid, step_mismatch, DEV_HUB missing → non-zero + diagnostic | s02, s04, s07 |
| NFR: security | fixed argv only; no shell=True; no user-controlled binary | s05, s08 |
| NFR: concurrency | one loop per project_root (flock in loop.sh; duplicate run → clear message) | s05 |
| NFR: idempotent filter | workspace filter view-only; ledger unchanged | s09 |
| NFR: model precedence | phase env wins over preset; documented in README | s03, s10 |
| NFR: async host | loop runs async; no blocking HTTP forever | s05, s08 |
| NFR: 014 schema import | board_launch imports card_model from board_sync (no drift) | s02 |

### SC покрытие

| SC | Описание | sNN |
| :--- | :--- | :--- |
| SC-001 | Arm меняет activeContext только в project_root карточки | s04 |
| SC-002 | Loop argv содержит abs project root + hub bin | s03, s05 |
| SC-003 | mb stock-run не создаёт ordinary agent prompt path | s08 |
| SC-004 | step_mismatch → exit ≠ 0 | s04 |
| SC-005 | Non-mb card stock run unchanged | s08 |
| SC-006 | Workspace filter hides non-matching cards client-side | s09 |
| SC-007 | Preset argv appended when phase env unset | s03 |
| SC-008 | Phase env set → preset not appended; diagnostic in result | s03 |

---

## Stages coverage (план-этапы → sNN)

| Этап плана | sNN |
| :--- | :--- |
| spike Cordis intercept vs alternate API | s01 |
| board_launch package + metadata parse + card_model import | s02 |
| build_loop_argv + model precedence + preset whitelist | s03 |
| arm_from_card + step_mismatch + gate arm rules | s04 |
| loop_run subprocess + Fake + execution result | s05 |
| arm_loop pipeline + syncAfterLoop | s06 |
| CLI hub-board arm/loop/arm-loop | s07 |
| dsh plugin mb-bridge Host bridge + intercept | s08 |
| Board controls UI (workspace filter + runtime + model presets + Sync) | s09 |
| Install script + docs runbook + regression suite | s10 |

---

## Outcome map (plan → steps)

| Outcome / Зачем | sNN |
| :--- | :--- |
| **Arm step/gate с доски**: activeContext продукта обновляется из карточки без ручного CLI | s04 |
| **Loop запускается через board**: тот же pipeline что `make loop`; fail-closed без bypass | s05, s06 |
| **Один клик Arm+Run**: arm then loop атомарно; короткий путь для разработчика | s06, s07 |
| **Нет stock agent bypass**: mb-card run redirect/deny; явная ошибка `mb_card_requires_loop_run` | s08 |
| **Модель управляемо**: env > preset > default; UI badge отражает источник; whitelist безопасность | s03, s09 |
| **Workspace фильтр**: видны только карточки нужного product root; ledger не изменён | s09 |
| **Cordis API решено**: s01 spike закрывает неопределённость до реализации; нет silent defer | s01 |
| **CLI parity**: hub-board arm/loop/arm-loop зеркалит UI flows; тестируем без DSH UI | s07 |
| **Docs + regression**: runbook + model precedence table + test_board_launch_*.py regression при изменении 014 | s10 |

---

## Replacement cleanup (plan → steps)

| Kind | Что устаревает | Замена | sNN deletes | Fallback? |
| :--- | :--- | :--- | :--- | :--- |
| A (code) | stock `HostExecutionRunner.launch` как primary для mb-* | mb-bridge loop-run intercept | s08 (`deletes`: intercept guard removes direct launch path for mb cards) | нет (fail-closed) |
| A (code) | Stub prompt «T-HUB-015 later» как единственный CTA (если есть в board_sync) | Arm/Run UI + CLI | s08 (rg-проверка: нет «T-HUB-015 later» stub в board) | нет (delete in-epic) |
| B (entrypoint) | `make loop` без board path (manual only) | board + `hub-board arm-loop` | — | оба валидны; keep |
| C (fallbacks) | Silent stock agent run when bridge misconfigured | fail-closed error | s08 (intercept enforces) | нет |
| C (fallbacks) | Soft ignore step_mismatch | hard fail | s04 (arm_from_card) | нет |

**Greenfield** (`loop/board_launch/`, `dsh/plugins/mb-bridge/`): все новые файлы → `deletes: []` в s02–s07, s09.
**Brownfield replace** (stock run intercept, stub prompt): s08 несёт `deletes` + rg anti-fallback cp.
**Purge sNN:** s08 содержит финальный anti-stub rg checkpoint — проверяет отсутствие bypass callers.
Из-за объёма replace только в s08 (intercept + stub removal) отдельный `*-legacy-fallback-purge` shard не нужен: s08 сам является cutover-шагом с rg cp.

---

## Queue (shards)

| sNN | File | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-spike-cordis-intercept-api-decision.yaml](s01-spike-cordis-intercept-api-decision.yaml) | no | no | BACK IMPLEMENT | completed |
| **s02** | [s02-board-launch-metadata-card-model.yaml](s02-board-launch-metadata-card-model.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-loop-argv-model-precedence.yaml](s03-loop-argv-model-precedence.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-arm-from-card-step-mismatch.yaml](s04-arm-from-card-step-mismatch.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-loop-run-subprocess-execution-result.yaml](s05-loop-run-subprocess-execution-result.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-arm-loop-pipeline-sync-after-loop.yaml](s06-arm-loop-pipeline-sync-after-loop.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-cli-hub-board-arm-loop-arm-loop.yaml](s07-cli-hub-board-arm-loop-arm-loop.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-dsh-plugin-mb-bridge-host-bridge.yaml](s08-dsh-plugin-mb-bridge-host-bridge.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s09** | [s09-board-controls-ui-workspace-filter-model-preset.yaml](s09-board-controls-ui-workspace-filter-model-preset.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s10** | [s10-docs-install-regression-suite.yaml](s10-docs-install-regression-suite.yaml) | no | no | BACK IMPLEMENT | completed |
| **s11** | [s11-audit-execution-recording.yaml](s11-audit-execution-recording.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s12** | [s12-audit-stock-run-intercept-wiring.yaml](s12-audit-stock-run-intercept-wiring.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s13** | [s13-audit-workspace-list-adapter.yaml](s13-audit-workspace-list-adapter.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s14** | [s14-audit-model-source-propagation.yaml](s14-audit-model-source-propagation.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s15** | [s15-audit-config-authorization-validation.yaml](s15-audit-config-authorization-validation.yaml) | no | yes | BACK IMPLEMENT | completed |
**Audit remediation:** s11–s15 are append-only shards from `audit-20260829-dsh-board-arm-loop.yaml`; they remain `pending` until BACK IMPLEMENT and a repeat BACK AUDIT.

**needs_creative:** все `no`. Cordis intercept API неопределённость закрыта spike в s01 (не CREATIVE — spike = исследование + документирование + реализация решения по факту API; если API нет → alternate route + docs documented in shard). CREATIVE не требуется.
