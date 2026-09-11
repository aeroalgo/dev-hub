# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-086-python-loop-supervisor-cutover
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-11
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../../../.cursor/templates/decompose/epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-086-python-loop-supervisor-cutover/md/decompose-index.md`. Machine = `plan/T-HUB-086-python-loop-supervisor-cutover/yaml/decompose-index.yaml`. Shards = `yaml/steps/`.
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | структура шагов, атомарность |
| `tdd` | characterization and regression tests |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator, я хочу запускать loop прежней командой `bin/loop`, чтобы миграция supervisor-а не требовала смены привычного workflow. | s02, s05 | Positional CLI parsing in s02, bin/loop delegation & E2E smoke in s05 |
| US-002 | Как maintainer, я хочу тестировать orchestration в pytest через Python API, чтобы не `source`-ить shell и не проверять implementation text. | s01, s04, s05 | Contract interfaces in s01, orchestrator unit tests in s04, test rewrite in s05 |
| US-003 | Как runtime maintainer, я хочу добавлять/менять adapter без нового provider-specific блока в supervisor-е. | s03 | Provider-neutral SessionInvoker in s03 |
| US-004 | Как operator, я хочу, чтобы timeout, Ctrl+C, retry cap, model substitution, missing binary и fail-closed halt сохранялись. | s02, s04, s07 | Signal traps in s02, outer retry / halt in s04, regression scan in s07 |
| US-005 | Как reviewer, я хочу видеть один canonical execution path и остаток shell только как shim. | s05, s06, s07 | Minimal shim in s05, doc migration in s06, sunset inventory purge in s07 |
| FR-001 | `loop.runner` предоставляет canonical `main(argv: Sequence[str] | None) -> int` и module execution через `python3 -m loop.runner`. | s01, s02 | Dataclasses/interfaces in s01, CLI/module entrypoint in s02 |
| FR-002 | CLI сохраняет positional/flag contract текущего `loop.sh`: project root resolution через `bin/loop`, epic spec, model, `implement`, `--epic`, `--phase GAP_FANOUT`, `--dag-generate`, permission mode, interactive/headless, verbose, status и help. | s02 | Argument parsing & flag parity |
| FR-003 | runner загружает `.claude/project.env`, `.local` и per-product overrides через Python helper; process env precedence и invalid runtime config semantics остаются явными и fail-closed. | s02 | Configuration bootstrap & env loader |
| FR-004 | runner вычисляет canonical `HUB_ROOT`, `PROJECT_ROOT`, `DEV_HUB`, `EPIC_PROJECT_ROOT`, `CLAUDE_PROJECT_DIR`, `STATE_DIR` и runtime-specific cwd до первого session call. | s02 | Path normalization & preflight checks |
| FR-005 | runner acquires one non-blocking checkout lock, publishes `runner.json` through existing atomic owner helper and removes owner only when pid/session id match. | s02 | RunnerLease & POSIX flock |
| FR-006 | signal handling for `SIGINT`, `SIGTERM`, `SIGHUP` releases owned process/owner state safely; user interrupt returns 130 and never enters transient outer retry. | s02 | Signal handling & exit codes |
| FR-007 | runner performs compile/doctor/preflight checks with explicit result objects; missing or invalid required code/config exits non-zero before session launch. | s01, s02 | Preflight check types in s01, execution in s02 |
| FR-008 | `SessionInvoker` resolves provider through runtime registry/adapters and invokes existing session-resilience boundary with explicit timeout, kill grace, heartbeat, idle timeout, log path, expected model, stdin and progress mode. | s03 | SessionInvoker & session resilience integration |
| FR-009 | Claude, DSH and Codex retain their current cwd, argv, profile, model, stdin and stream-filter behavior; missing DSH/Codex binary has no silent Claude fallback. | s03 | Runtime adapters & binary resolution |
| FR-010 | outer loop performs `prepare`, session invocation, `record-session`, bounded transient retry with re-prepare, and `check-after` in the same order as current behavior. | s04 | LoopRunner state machine |
| FR-011 | action decision is centralized through `halt_logic.decide_after_action`; `continue`, `complete`, `halt`, `NEED_HUMAN`, `EPIC_DONE`, DAG fanout and optional roadmap continuation remain observable. | s04 | Action dispatch & halt logic integration |
| FR-012 | session log pruning, runtime trace/incident updates, Tier-1 incident attempt and terminal status output are either invoked through existing Python helpers or explicitly preserved in runner collaborators; no behavior is dropped as “cleanup”. | s04 | Incident tracking, log pruning & terminal output |
| FR-013 | `loop/loop.sh` contains only path resolution, `cd` to hub and `exec python3 -m loop.runner`; it exposes no production orchestration functions. | s05, s07 | Minimal exec shim in s05, verification in s07 |
| FR-014 | every former shell-source test is rewritten to public CLI or importable Python API behavior; no test depends on implementation text in `loop.sh`. | s05, s07 | Test suite rewrite in s05, verification in s07 |
| FR-015 | active operator/instruction docs teach `bin/loop` or `python3 -m loop.runner`; direct `loop.sh` references are labeled compatibility-only and no document teaches `source loop.sh` functions. | s06, s07 | Documentation migration in s06, purge scan in s07 |
| FR-016 | full targeted runner/runtime suite and shell syntax/public entrypoint smoke pass; no new external dependency is introduced. | s07 | Full targeted regression suite & sunset scan |
| SC-001 | `bin/loop --help`, `bin/loop <project> --status` and direct `loop/loop.sh --help` resolve through Python runner and exit 0. | s02, s05 | CLI parser in s02, launcher delegation in s05 |
| SC-002 | One fake public loop turn reaches session and terminal decision with no shell function sourcing. | s04, s05 | LoopRunner in s04, E2E runner tests in s05 |
| SC-003 | Claude/DSH/Codex runtime-specific command and failure behavior remains green. | s02, s03 | Preflight checks in s02, adapter execution in s03 |
| SC-004 | `rg` finds zero production callers of removed shell orchestration symbols and zero `source loop/loop.sh` in active tests/instructions. | s05, s06, s07 | Removal in s05, docs in s06, grep control in s07 |
| SC-005 | Timeout, interrupt, retry cap, model substitution, missing binary, lock contention and fail-closed `check-after` have executable evidence. | s01, s02, s03, s04, s07 | Failure test matrix across s01-s04 & verified in s07 |
| SC-006 | No second supervisor path remains; `loop.sh` is a delegation shim under 30 non-comment lines. | s05, s07 | Shim replacement in s05, verification in s07 |
| AC+ #1 | `python3 -m loop.runner --help` and `loop/loop.sh --help` return 0 and show the same operator-relevant options. | s02, s05 | |
| AC+ #2 | `bin/loop` resolves a product root exactly as before, then delegates to one Python entrypoint; no shell runner logic is executed after delegation. | s02, s05 | |
| AC+ #3 | `--status`, `--dag-generate`, `--phase GAP_FANOUT` and `doctor` paths remain non-session commands and preserve their existing output/exit contracts. | s02 | |
| AC+ #4 | A normal fake Claude/DSH/Codex session goes through existing adapter and session-resilience contracts, writes the expected log, and returns the runtime exit code to `record-session`. | s03, s04 | |
| AC+ #5 | A transient abort re-prepares context before retry, respects configured retry cap/backoff, and resumes outer prepare when cap is reached. | s04 | |
| AC+ #6 | A permanent failure, model substitution, missing runtime binary, invalid config or DSH profile failure halts non-zero without provider fallback. | s02, s03, s04 | |
| AC+ #7 | `SIGINT`/`SIGTERM` does not cause an outer retry; owned `runner.json` is cleaned only by the owning pid/session identity. | s02 | |
| AC+ #8 | `check-after` action selection is delegated to `halt_logic.decide_after_action`, and `NEED_HUMAN`/fail-closed halt is not converted into blind continue. | s04 | |
| AC+ #9 | Existing runtime state paths, session log retention, `last-session.json`, trace/incident artifacts and checkpoint ownership remain unchanged. | s04 | |
| AC+ #10 | Public behavior tests do not source `loop.sh`, invoke shell functions, or assert implementation text as the only evidence. | s05 | |
| AC+ #11 | Active docs and instruction surfaces no longer present shell orchestration as the canonical machine path. | s06 | |
| AC+ #12 | The final purge scan has no A/B/C/I leftovers and the runner shim has exactly one production caller path. | s05, s07 | |
| AC− #1 | Нет второго исполняемого supervisor-а с отдельным outer `while`, retry policy или `check-after` decision tree. | s04, s05, s07 | |
| AC− #2 | Нет `source loop/loop.sh` в production instructions/tests; shell functions не являются API. | s05, s06, s07 | |
| AC− #3 | Нет `python3 -c`/shell text extraction для machine JSON, runtime result или owner state. | s02, s03, s04 | |
| AC− #4 | Нет `try new except old`, automatic fallback Python → shell или unknown runtime → Claude. | s03, s07 | |
| AC− #5 | Misconfiguration, missing binary, invalid adapter, lock contention and malformed result produce explicit non-zero/fail-closed outcome. | s02, s03, s04 | |
| AC− #6 | Нет active instruction surface, которая требует чтения/ручного редактирования runner files вместо public status/doctor/CLI. | s06 | |
| AC− #7 | Нет obsolete tests, которые вынуждают вернуть удалённый shell contract ради green suite. | s05, s07 | |
| AC− #8 | Нет изменения state/telemetry semantics, замаскированного под migration; contract regressions are failures, not accepted migration differences. | s04, s07 | |
| TM-086-01 | `bin/loop --help` and `python3 -m loop.runner --help` expose the same public options. | s02, s05 | CLI parity matrix |
| TM-086-02 | `--status`, `--dag-generate`, `--phase GAP_FANOUT` and `doctor` remain non-session commands. | s02 | Non-session command matrix |
| TM-086-03 | Canonical runtime paths and environment precedence are resolved before session launch. | s02 | Configuration and path matrix |
| TM-086-04 | Lock contention and owner cleanup remain fail-closed and identity-safe. | s02 | Ownership matrix |
| TM-086-05 | SIGINT, SIGTERM and SIGHUP preserve signal exit and cleanup behavior. | s02 | Signal matrix |
| TM-086-06 | Claude, DSH and Codex retain runtime-specific argv, cwd, stdin and stream behavior. | s03 | Adapter matrix |
| TM-086-07 | Missing or invalid runtime binaries never fall back to Claude. | s03, s07 | Fail-closed runtime matrix |
| TM-086-08 | Session timeout, kill grace, heartbeat and idle timeout cross the typed invocation boundary. | s03 | Session boundary matrix |
| TM-086-09 | Outer prepare, invocation, record-session, retry and check-after lifecycle order is preserved. | s04 | Orchestration matrix |
| TM-086-10 | `halt_logic.decide_after_action` preserves continue, complete, halt and human-intervention decisions. | s04 | Halt decision matrix |
| TM-086-11 | `loop.sh` and `bin/loop` delegate through one Python execution path under the shim threshold. | s05, s07 | Cutover matrix |
| TM-086-12 | Legacy shell callers, source-based tests and active instruction fallbacks are absent. | s05, s06, s07 | Sunset matrix |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Stage 1 — contract characterization and runner seams | plan §Stage 1 | s01 |
| Stage 2 — Python composition root and configuration/ownership | plan §Stage 2 | s02 |
| Stage 3 — provider-neutral session invocation | plan §Stage 3 | s03 |
| Stage 4 — outer orchestration migration | plan §Stage 4 | s04 |
| Stage 5 — cutover and compatibility shims | plan §Stage 5 | s05 |
| Stage 6 — active instruction/docs migration | plan §Stage 6 | s06 |
| Stage 7 — final legacy purge and QA evidence | plan §Stage 7 | s07 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Single canonical Python composition root (`python3 -m loop.runner`) | s01, s02 |
| POSIX flock ownership and signal-safe cleanup (`SIGINT` -> 130) | s02 |
| Provider-neutral session invocation without shell branching | s03 |
| Outer loop lifecycle, transient retry backoff, check-after action dispatch | s04 |
| Cutover `loop.sh` to <30 lines exec shim, wire `bin/loop`, rewrite tests | s05 |
| Migrate active docs, commands, and runbooks to Python supervisor | s06 |
| Full A/B/C/I sunset inventory scan and targeted regression suite | s07 |
| Machine-boundary ladder: add typed runner → wire public caller → enforce Python-only path → legacy-fallback-purge | s01, s02, s05, s07 |
| Out of scope (historical archive rewrite, new provider capabilities, parallel DAG) | — |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `loop/loop.sh:ensure_dsh_profiles` | A | `loop/runner/config.py` + DSH adapter | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:configure_runtime_env` | A | `RunnerConfig.from_environment` | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:find_claude` | A | adapter binary resolution | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:is_epic_spec` and shell positional parser | A | `loop/runner/cli.py` parser | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:_cleanup_runner_owner` | A | `RunnerLease` ownership | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:run_claude_session` | A | `SessionInvoker.invoke` + Claude adapter | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:resolve_dsh_bin` | A | `loop/runtime_adapters/dsh.py` | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:run_dsh_session` | A | `SessionInvoker.invoke` + DSH adapter | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:run_agent_session` | A | `SessionInvoker` invocation | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:_print_prepare_summary` | A | `loop/runner/output.py` | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:_print_prepare_summary / _apply_prepare_session_vars` | A | `loop/runner/output.py` + `RunnerConfig` | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:_run_context_prepare` | A | `LoopRunner.prepare` | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh:_run_context_prepare / _reprepare_for_transient_retry` | A | `LoopRunner.prepare` retry lifecycle | s05, s07 | no | delete in s05, scan in s07 |
| `loop/loop.sh` outer while true loop | A | `LoopRunner.run` | s05, s07 | no | delete in s05, scan in s07 |
| shell-source tests in `test_loop_dsh_dispatch.py` etc. | A | public CLI / Python API tests | s05, s07 | no | rewritten in s05, scan in s07 |
| `loop/loop.sh` as full supervisor | B | `loop/loop.sh` exec shim | s05, s07 | no | rewritten in s05, scan in s07 |
| `bin/loop` -> shell full runner assumption | B | `bin/loop` -> Python composition root | s05, s07 | no | rewritten in s05, scan in s07 |
| direct `source loop/loop.sh` test/operator API | B | `bin/loop` or `python3 -m loop.runner` | s05, s07 | no | deleted in s05, scan in s07 |
| `python3 -c ... 2>/dev/null || true` env parsing | C | `load_project_env` fail-closed | s02, s07 | yes | fail-closed in s02, scan in s07 |
| `echo JSON | python3 -c ... || echo raw` action parsing | C | typed result parser | s04, s07 | yes | fail-closed in s04, scan in s07 |
| inline Python heredocs and repeated `python3 -c` JSON parsers in `loop.sh` | C | typed Python runner parsers | s02, s04, s07 | no | delete in s05, scan in s07 |
| shell branch default runtime to Claude | C | fail-closed `InvalidRuntimeConfig` | s03, s07 | yes | fail-closed in s03, scan in s07 |
| Python runner exception fallback to `loop.sh` | C | fail-closed non-zero exit | s04, s07 | yes | fail-closed in s04, scan in s07 |
| DSH missing binary fallback to Claude | C | explicit exit 127 / halt | s03, s07 | yes | fail-closed in s03, scan in s07 |
| docs/instructions teaching `loop.sh` internals | I | docs teaching `bin/loop` & `python3 -m loop.runner` | s06, s07 | no | rewritten in s06, scan in s07 |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-contracts-and-seams.yaml](../yaml/steps/s01-contracts-and-seams.yaml) | [s01…](../../implement/T-HUB-086-python-loop-supervisor-cutover/s01-contracts-and-seams.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-config-and-ownership.yaml](../yaml/steps/s02-config-and-ownership.yaml) | [s02…](../../implement/T-HUB-086-python-loop-supervisor-cutover/s02-config-and-ownership.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-provider-neutral-session-invoker.yaml](../yaml/steps/s03-provider-neutral-session-invoker.yaml) | [s03…](../../implement/T-HUB-086-python-loop-supervisor-cutover/s03-provider-neutral-session-invoker.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-outer-orchestrator-and-lifecycle.yaml](../yaml/steps/s04-outer-orchestrator-and-lifecycle.yaml) | [s04…](../../implement/T-HUB-086-python-loop-supervisor-cutover/s04-outer-orchestrator-and-lifecycle.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-cutover-and-compatibility-shims.yaml](../yaml/steps/s05-cutover-and-compatibility-shims.yaml) | [s05…](../../implement/T-HUB-086-python-loop-supervisor-cutover/s05-cutover-and-compatibility-shims.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-active-instructions-and-docs.yaml](../yaml/steps/s06-active-instructions-and-docs.yaml) | [s06…](../../implement/T-HUB-086-python-loop-supervisor-cutover/s06-active-instructions-and-docs.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-legacy-fallback-purge.yaml](../yaml/steps/s07-legacy-fallback-purge.yaml) | [s07…](../../implement/T-HUB-086-python-loop-supervisor-cutover/s07-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |