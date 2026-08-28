# decompose-T-HUB-006-dsh-loop-runtime-adapter / index.md

**Plan:** [plan-T-HUB-006-dsh-loop-runtime-adapter.md](../plan-T-HUB-006-dsh-loop-runtime-adapter.md)  
**Role:** BACK  
**Status tracker (canon):** [index.yaml](index.yaml)  
**Дата:** 2026-08-22  

---

## Outcome map (plan → steps)

| Outcome | Зачем | sNN |
|---------|-------|-----|
| Единый env-флаг `EPIC_RUNTIME` переключает executor Claude↔DSH без изменения default | Оператор меняет runtime одной строкой; product pipeline не требует fork loop.sh | s01, s02 |
| `loop.sh` диспетчеризует `run_agent_session` → `run_claude_session` \| `run_dsh_session` | Чистое разделение инвокации без дублирования session_resilience | s03, s04 |
| `loop/runtime_adapters/dsh.py`: `build_command()` + `normalize_log_for_analysis()` | Изоляция DSH CLI integration в одном модуле; легко переписать при смене DSH API | s02, s04 |
| `analyze_session_log` понимает DSH log (completed / transient / permanent) | `record-session` + retry logic работают с DSH так же как с Claude | s05 |
| `prepare_session` эмитирует `runtime`, `dsh_profile`, `dsh_workspace` | Агент/оркестратор видит контракт без чтения env | s03 |
| Scaffold `dsh/` — README + `which-dsh.sh` + `profiles/.gitkeep` | T-HUB-007 может добавить профили без PR на loop core | s06 |
| Regression suite для Claude path — зелёный | Нулевая регрессия; CI = gate перед production pilot | s01, s07 |
| Unit + integration tests: command builder, log normalizer, runtime config, fake-dsh e2e | TDD red→green до shell wiring; CI enforceable | s01, s02, s05, s07 |

---

## Requirements coverage (plan → steps)

### FR

| ID | Требование | sNN | Статус |
|----|------------|-----|--------|
| FR-1 | `EPIC_RUNTIME` ∈ `{claude, dsh}`; invalid → `invalid_runtime_config` fail-closed при старте loop | s01 | covered |
| FR-2 | CLI loop: `--runtime claude\|dsh` override env | s03 | covered |
| FR-3 | `loop.sh`: `run_agent_session()` dispatch → `run_claude_session` \| `run_dsh_session` | s04 | covered |
| FR-4 | `run_dsh_session`: invoke `dsh --profile epic-${LOOP_PHASE}`; log → `$STATE_DIR/session-${iter}.log` | s04 | covered |
| FR-5 | `prepare` JSON: поля `runtime`, `dsh_profile`, `dsh_workspace` | s03 | covered |
| FR-6 | `loop/runtime_adapters/dsh.py`: `build_command()`, `normalize_log_for_analysis(raw) → text` | s02 | covered |
| FR-7 | `analyze_session_log` ветка `runtime=dsh` — detect completed / transient / permanent | s05 | covered |
| FR-8 | `record-session` корректно classifies DSH exit 0 + incomplete FINISH как abort | s05 | covered |
| FR-9 | Scaffold `dsh/README.md` + `dsh/profiles/.gitkeep` + `dsh/bin/which-dsh.sh` | s06 | covered |
| FR-10 | Unit tests: command builder, log normalizer, runtime config validation | s01, s02, s07 | covered |

### NFR

| ID | Требование | sNN | Статус |
|----|------------|-----|--------|
| NFR-1 | Zero regression: `EPIC_RUNTIME` unset → byte-identical Claude code path | s07 | covered |
| NFR-2 | Timeout/retry: тот же `session_resilience.py` wrapper вокруг DSH subprocess | s04 | covered |
| NFR-3 | Model substitution HALT: для DSH phase — отдельная detection (adapter mismatch), не Claude org message | s05 | covered |
| NFR-4 | TDD: red→green на pure functions до shell wiring | s01, s02, s05 | covered |
| NFR-5 | Do Not Touch: flock, roadmap-advance, DAG, prepare halt matrix | all shards — out_of_scope | covered |

### AC+

| ID | AC | sNN |
|----|----|-----|
| AC+1 | `EPIC_RUNTIME=dsh` + mock `dsh` script → loop invokes mock with `--profile epic-implement` and prompt body | s04, s07 |
| AC+2 | `EPIC_RUNTIME=claude` (default) → existing tests green | s01, s07 |
| AC+3 | Unit: invalid `EPIC_RUNTIME=foo` → loop exit 2 + diagnostic | s01 |
| AC+4 | Unit: DSH log fixture → `analyze_session_log` → `outcome=completed` vs `aborted` vs `retryable` | s05 |
| AC+5 | `dsh/README.md` documents Node version, `DEEPSEEK_API_KEY`, `EPIC_RUNTIME=dsh` | s06 |
| AC+6 | Missing `dsh` binary when runtime=dsh → fail-closed message (not silent fallback to Claude) | s04 |

### AC−

| ID | AC | Coverage |
|----|----|---------|
| AC−1 | Не менять default на dsh | s01: EPIC_RUNTIME default=`claude`; NFR-1; s07 regression |
| AC−2 | Не удалять Claude path | s04: `run_claude_session` остаётся, обёртка добавляется |
| AC−3 | Не монтировать Cordis plugins (→ T-HUB-008) | out_of_scope во всех шагах |
| AC−4 | Не дублировать epic state logic в DSH adapter | s02: adapter = pure fn (build_command, normalize); state в context_loop.py |
| AC−5 | Не требовать DSH для `make loop ARGS=gpt` | s01: guard на EPIC_RUNTIME=dsh; fail-closed только при dsh |

---

## Stages coverage (plan фазы → sNN)

| Фаза плана | sNN | Title |
|-----------|-----|-------|
| s01 — runtime config + TDD validation | s01 | EPIC_RUNTIME validation + fail-closed unit tests |
| s02 — `loop/runtime_adapters/dsh.py` + fixtures | s02 | DSH adapter module: build_command + normalize_log |
| s03 — prepare JSON fields + `--runtime` CLI | s03 | prepare runtime fields + `--runtime` CLI override |
| s04 — `run_dsh_session` in loop.sh + fake dsh integration test | s04 | run_dsh_session + run_agent_session dispatch in loop.sh |
| s05 — `analyze_session_log` DSH branch + record-session | s05 | analyze_session_log DSH branch + record-session classify |
| s06 — dsh/README scaffold + stub profile note | s06 | dsh/ scaffold: README + which-dsh.sh + profiles/.gitkeep |
| s07 — regression suite + smoke | s07 | Regression suite: Claude path + end-to-end fake-dsh smoke |

---

## Replacement cleanup (plan → steps)

Эпик **greenfield extension**: не заменяет существующий модуль, только добавляет ветку дисптатчинга и новый пакет `runtime_adapters/`.

| Kind | Что | Действие | sNN | Fallback? |
|------|-----|----------|-----|-----------|
| A (rename) | `run_claude_session` → внутренняя; добавить обёртку `run_agent_session` | Обёртка в s04; `run_claude_session` остаётся как внутренняя функция — без deletes | s04 | n/a — wrapper call, не rename |
| B (new files, не replace) | `loop/runtime_adapters/__init__.py`, `loop/runtime_adapters/dsh.py` | Create; нет callers до s04 | s02 | n/a |
| C (extend, не replace) | `_lib.py::resolve_runtime_config`, `context_loop.py::prepare_session`, `session_resilience.py::analyze_session_log` | Extend with new branch; old branch untouched | s01, s03, s05 | n/a — additive branch |

Нет удалений существующего кода → **`deletes: []`** у всех шагов кроме s04 (где `run_claude_session` оборачивается, не удаляется).  
**Нет legacy-fallback-purge**: нет replace A→B pattern; нет brownfield sunset. Строка `n/a` корректна.

---

## Очередь шагов

| ID | File | Title | Phase | Status |
|----|------|-------|-------|--------|
| s01 | s01-runtime-config-validation.yaml | EPIC_RUNTIME validation + fail-closed unit tests | BACK IMPLEMENT | pending |
| s02 | s02-dsh-adapter-module.yaml | DSH adapter module: build_command + normalize_log | BACK IMPLEMENT | pending |
| s03 | s03-prepare-runtime-fields.yaml | prepare runtime fields + --runtime CLI override | BACK IMPLEMENT | pending |
| s04 | s04-run-dsh-session-loop-dispatch.yaml | run_dsh_session + run_agent_session dispatch in loop.sh | BACK IMPLEMENT | pending |
| s05 | s05-analyze-session-log-dsh-branch.yaml | analyze_session_log DSH branch + record-session classify | BACK IMPLEMENT | pending |
| s06 | s06-dsh-scaffold.yaml | dsh/ scaffold: README + which-dsh.sh + profiles/.gitkeep | BACK IMPLEMENT | pending |
| s07 | s07-regression-suite.yaml | Regression suite: Claude path + end-to-end fake-dsh smoke | BACK IMPLEMENT | pending |

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | EPIC_RUNTIME validation + fail-closed unit tests — runtime config guard · [yaml](s01-runtime-config-validation.yaml) | BACK IMPLEMENT | completed |
| **s02** | DSH adapter module: build_command + normalize_log — pure fn isolation · [yaml](s02-dsh-adapter-module.yaml) | BACK IMPLEMENT | completed |
| **s03** | prepare runtime fields + --runtime CLI override — orchestrator contract · [yaml](s03-prepare-runtime-fields.yaml) | BACK IMPLEMENT | completed |
| **s04** | run_dsh_session + run_agent_session dispatch — loop.sh executor branch · [yaml](s04-run-dsh-session-loop-dispatch.yaml) | BACK IMPLEMENT | completed |
| **s05** | analyze_session_log DSH branch + record-session classify — resilience parity · [yaml](s05-analyze-session-log-dsh-branch.yaml) | BACK IMPLEMENT | completed |
| **s06** | dsh/ scaffold: README + which-dsh.sh + profiles/.gitkeep — T-HUB-007 landing pad · [yaml](s06-dsh-scaffold.yaml) | BACK IMPLEMENT | completed |
| **s07** | Regression suite: Claude path + end-to-end fake-dsh smoke — NFR-1 green · [yaml](s07-regression-suite.yaml) | BACK IMPLEMENT | completed |
| **s08** | Audit remediation: DSH resolver argv compatibility — FR-4 · [yaml](s08-audit-dsh-resolver-argv.yaml) | BACK IMPLEMENT | completed |
| **s09** | Audit remediation: DSH model-substitution HALT detection — NFR-3 · [yaml](s09-audit-dsh-model-mismatch.yaml) | BACK IMPLEMENT | completed |