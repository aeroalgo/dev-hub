# [T-HUB-086 | python-loop-supervisor-cutover] PLAN

**Дата:** 2026-09-08  
**Режим:** BACK PLAN  
**Уровень:** L4  
**Статус:** draft  
**Clarify:** Phase 0 skipped — taxonomy clear: пользователь подтвердил направление «Python supervisor + совместимый shell shim» предыдущим сообщением и запросом BACK PLAN.  
**Deps:** hard `T-HUB-079` — lifecycle/terminal telemetry contract; existing runtime adapter contracts from `T-HUB-042`/`T-HUB-043` are consumed, not redesigned.  
**Prompt:** [md/prompt.md](prompt.md) — outcome SoT, абстрактнее HOW.

## Контекст

- `loop/loop.sh` вырос до крупного process supervisor: parser, environment bootstrap, runtime resolution, lock/owner lifecycle, signal handling, session invocation, stream filters, retries, `prepare → session → record → check-after`, incident Tier-1 retry и DAG/roadmap continuation находятся в одном shell-файле.
- `loop/context_loop.py` уже владеет domain/state operations: `arm`, `prepare`, `record-session`, `check-after`, `status`, DAG, roadmap и doctor CLI.
- `loop/runtime/dispatch.py` и `loop/runtime_adapters/*` уже владеют runtime-specific argv/analyze contracts для Claude, DSH и Codex.
- `harness/hooks/session_resilience.py` уже владеет bounded subprocess execution, process-group timeout/kill, log capture, idle watchdog, model-substitution detection и abort classification.
- Текущий shell supervisor дублирует Python boundary: вызывает `python3 -c` для JSON/env/owner parsing, держит runtime-specific branching и содержит тестируемые только через `source loop/loop.sh` функции.
- Цель эпика — сделать Python supervisor единственным исполняющим SoT, сохранив внешний операторский контракт `bin/loop`, публичные exit-коды, runtime state paths, logs, retry/halt/complete semantics и direct `loop/loop.sh` compatibility entrypoint.

### Область задачи

В scope:

1. Новый canonical Python runner package с typed internal interfaces.
2. Перенос orchestration/process-supervision logic из `loop/loop.sh`.
3. Интеграция с существующими `context_loop`, runtime registry/adapters и `session_resilience` без повторной реализации их domain logic.
4. Тонкий `loop/loop.sh` compatibility shim и сохранение `bin/loop` как operator-facing launcher.
5. Переписывание shell-source tests в public CLI/API tests.
6. Обновление активных operator/instruction/architecture surfaces, которые называют shell orchestration каноническим путем.
7. Полный A/B/C/I sunset inventory и fail-closed purge evidence.

Вне scope:

- Новый runtime/provider и изменение поведения Claude, DSH или Codex.
- Изменение формата `activeContext.md`, decompose index, checkpoint, `last-session.json`, `state.json`, episode packages или gate verdict.
- Переписывание `context_loop.py` domain state machine.
- Переписывание алгоритма `session_resilience.run_session` или provider-specific stream filter formats; допускается только добавление узкого callable/API, если оно нужно для Python caller.
- Изменение lifecycle semantics `T-HUB-079`; новый runner должен их потреблять.
- Параллельное выполнение DAG nodes или несколько runner slots на один checkout.
- Удаление `bin/loop` или `loop/loop.sh` как совместимых public entrypoints.
- Коммит, deploy, изменение product repositories и автоматическая миграция чужих runtime directories.

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Python supervisor запускает один полный loop turn | `vertical_slice` | `bin/loop` → `loop/loop.sh` shim → `python3 -m loop.runner` | `prepare → session → record-session → check-after`; `continue`, `complete`, `halt` сохраняют exit/stop behavior | fake runtime через public `bin/loop` выполняет bounded turn и пишет session evidence | `n/a` |
| Public CLI parity | `vertical_slice` | operator `bin/loop <project> [args]` и direct `loop/loop.sh [args]` | invalid args/config/runtime дают non-zero; `--help`, `--status`, `--doctor`, DAG commands не запускают unintended session | `loop/tests/test_runner_cli.py` subprocess tests | `n/a` |
| Runtime dispatch без shell runtime tree | `vertical_slice` | Python `SessionInvoker` вызывает registry adapter и session wrapper | unknown runtime, missing binary, model substitution и DSH install failure fail closed; Claude fallback запрещён | `loop/tests/test_runner_session.py` + fake Claude/DSH/Codex fixtures | `n/a` |

## Technology axiom (replace-not-wrap)

Эпик меняет machine boundary supervisor-а. Primary path проектируется как Python API/process supervisor; существующий shell читается только для sunset inventory и parity characterization.

| Выбор | Machine input / boundary | Обязательное следствие | FORBIDDEN после эпика |
|---|---|---|---|
| Python package как canonical supervisor | `RunnerConfig`, `SessionRequest`, `SessionResult`, typed enums/dataclasses и `list[str]` argv | orchestration state transitions и process handling находятся в Python-модулях, покрываются pytest без `source` | основная orchestration в shell; shell `while` как второй runtime path |
| Runtime registry/adapters как provider boundary | `RuntimeAdapter` + `SessionContext` + adapter-produced argv/analysis | новый runner вызывает registry/adapter contract, не добавляет `if runtime == ...` для каждого provider | новая provider-specific ветка в `loop.sh` или общий runner с Claude/DSH/Codex duplicated trees |
| Existing session resilience as process boundary | `session_resilience.run_session` API/CLI, bounded timeout/kill/log contract | runner передаёт explicit `SessionRequest`, сохраняет session log and result classification | второй timeout/kill implementation в runner или unbounded `subprocess.run` provider path |
| JSON only at explicit CLI/state boundaries | `context_loop` result dicts and durable JSON files; Python parses with `json.loads`/typed normalization | один parse point и explicit error result; no text slicing for machine state | `python3 -c`, `grep`/regex extraction of JSON, silent parse fallback to Claude/default |
| Compatibility through delegation | `loop.sh` and `bin/loop` remain thin launchers | old operator command delegates to one Python entrypoint and is covered by public smoke | shell shim exposing callable orchestration functions, `source` as production API, fallback from Python to shell |

## Продуктовая спека (WHAT)

## Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|---|---|---|
| 1 | Reframe: какую реальную проблему решаем? | Оператору и maintainers нужен предсказуемый loop supervisor, который можно тестировать и расширять без shell quoting/`set -e` ловушек; речь не о новой возможности продукта. | Эпик — brownfield runtime cutover, а не новый runtime и не redesign state machine. |
| 2 | Narrowest wedge: какой минимум доказывает гипотезу? | Один Python `LoopRunner` выполняет текущий `prepare → session → record → check-after` через fake runtime; `bin/loop` и `loop.sh` делегируют ему. | Сначала переносится vertical slice, затем docs/purge; не делать параллельную «новую архитектуру» без production caller. |
| 3 | Pre-mortem: почему решение провалится через месяц? | Потеряются signal/exit/filter/retry semantics, а старые shell tests будут зелёными только потому, что продолжают вызывать shell functions. | Characterization tests до cutover, typed result contract, fake provider fixtures и independent public-entrypoint QA обязательны. |
| 4 | Distribution/adoption: как оператор начнёт использовать новый путь? | Никак специально: `bin/loop` остаётся прежним. Для maintainers canonical development command/documentation становится `python3 -m loop.runner`, а direct `loop.sh` остаётся только compatibility wrapper. | Не менять user-facing invocation; убрать обучение source-based shell API. |
| 5 | Technical leverage: что можно не переписывать? | `context_loop.py`, runtime registry/adapters, stream filters, `session_resilience` и существующие runtime fixtures уже содержат нужные contracts. | Runner должен orchestrate existing contracts, а не копировать state/provider logic. |
| 6 | Appetite check: что вырезать первым при превышении бюджета? | В первую очередь не делать красивый unified output renderer и массовый historical-doc rewrite; сохраняются behavior, public CLI, state/lock/retry and active instruction correctness. | Timebox 5 дней; optional polish вне AC, core purge не вырезается. |

### User Stories

| # | Story | Priority | Independent Test |
|---|---|---|---|
| US-001 | Как operator, я хочу запускать loop прежней командой `bin/loop`, чтобы миграция supervisor-а не требовала смены привычного workflow. | P0 | Public subprocess smoke с fake runtime проверяет argv, state dir, log и terminal action. |
| US-002 | Как maintainer, я хочу тестировать orchestration в pytest через Python API, чтобы не `source`-ить shell и не проверять implementation text. | P0 | Unit/integration tests создают `RunnerConfig`/fake collaborators и проверяют result/action contracts. |
| US-003 | Как runtime maintainer, я хочу добавлять/менять adapter без нового provider-specific блока в supervisor-е. | P0 | Registry fake adapter проходит `SessionInvoker`; `rg` запрещённого runtime branching в runner/shell возвращает 0. |
| US-004 | Как operator, я хочу, чтобы timeout, Ctrl+C, retry cap, model substitution, missing binary и fail-closed halt сохранялись. | P0 | Failure matrix tests на fake process/logs и public CLI проверяют non-zero/continue/halt outcomes. |
| US-005 | Как reviewer, я хочу видеть один canonical execution path и остаток shell только как shim. | P1 | `sot_enforce_scan` и instruction scan подтверждают отсутствие shell orchestration callers/functions. |

#### Acceptance Scenarios — US-001

- **Given:** product root с `memory-bank/`, fake runtime и чистый runner state.
- **When:** оператор запускает `bin/loop <product> <model>`.
- **Then:** Python runner выполняет тот же lifecycle, пишет `runtime/<slug>/epic/session-*.log`, возвращает тот же terminal code и не запускает shell orchestration.

#### Acceptance Scenarios — US-002

- **Given:** fake `ContextPort`, fake `SessionInvoker` и deterministic `RecordResult`.
- **When:** `LoopRunner.run()` получает `continue`, `complete`, transient retry и halt outcomes.
- **Then:** каждый outcome выбирает ровно предусмотренное действие, без process shell и без скрытого retry.

#### Acceptance Scenarios — US-003

- **Given:** runtime id зарегистрирован в `loop/runtime_registry.yaml` и adapter реализует `RuntimeAdapter`.
- **When:** runner строит session request.
- **Then:** adapter возвращает argv/metadata, runner не знает provider-specific command shape, unknown id завершается fail-closed.

#### Acceptance Scenarios — US-004

- **Given:** fake session возвращает timeout, signal 130/143, transient abort, permanent failure или model substitution.
- **When:** runner классифицирует session result.
- **Then:** retry/outer continue/halt совпадают с текущим contract, а Ctrl+C не превращается в бесконечный outer retry.

### Functional Requirements

- **FR-001:** `loop.runner` предоставляет canonical `main(argv: Sequence[str] | None) -> int` и module execution через `python3 -m loop.runner`.
- **FR-002:** CLI сохраняет positional/flag contract текущего `loop.sh`: project root resolution через `bin/loop`, epic spec, model, `implement`, `--epic`, `--phase GAP_FANOUT`, `--dag-generate`, permission mode, interactive/headless, verbose, status и help.
- **FR-003:** runner загружает `.claude/project.env`, `.local` и per-product overrides через Python helper; process env precedence и invalid runtime config semantics остаются явными и fail-closed.
- **FR-004:** runner вычисляет canonical `HUB_ROOT`, `PROJECT_ROOT`, `DEV_HUB`, `EPIC_PROJECT_ROOT`, `CLAUDE_PROJECT_DIR`, `STATE_DIR` и runtime-specific cwd до первого session call.
- **FR-005:** runner acquires one non-blocking checkout lock, publishes `runner.json` through existing atomic owner helper and removes owner only when pid/session id match.
- **FR-006:** signal handling for `SIGINT`, `SIGTERM`, `SIGHUP` releases owned process/owner state safely; user interrupt returns 130 and never enters transient outer retry.
- **FR-007:** runner performs compile/doctor/preflight checks with explicit result objects; missing or invalid required code/config exits non-zero before session launch.
- **FR-008:** `SessionInvoker` resolves provider through runtime registry/adapters and invokes existing session-resilience boundary with explicit timeout, kill grace, heartbeat, idle timeout, log path, expected model, stdin and progress mode.
- **FR-009:** Claude, DSH and Codex retain their current cwd, argv, profile, model, stdin and stream-filter behavior; missing DSH/Codex binary has no silent Claude fallback.
- **FR-010:** outer loop performs `prepare`, session invocation, `record-session`, bounded transient retry with re-prepare, and `check-after` in the same order as current behavior.
- **FR-011:** action decision is centralized through `halt_logic.decide_after_action`; `continue`, `complete`, `halt`, `NEED_HUMAN`, `EPIC_DONE`, DAG fanout and optional roadmap continuation remain observable.
- **FR-012:** session log pruning, runtime trace/incident updates, Tier-1 incident attempt and terminal status output are either invoked through existing Python helpers or explicitly preserved in runner collaborators; no behavior is dropped as “cleanup”.
- **FR-013:** `loop/loop.sh` contains only path resolution, `cd` to hub and `exec python3 -m loop.runner`; it exposes no production orchestration functions.
- **FR-014:** every former shell-source test is rewritten to public CLI or importable Python API behavior; no test depends on implementation text in `loop.sh`.
- **FR-015:** active operator/instruction docs teach `bin/loop` or `python3 -m loop.runner`; direct `loop.sh` references are labeled compatibility-only and no document teaches `source loop.sh` functions.
- **FR-016:** full targeted runner/runtime suite and shell syntax/public entrypoint smoke pass; no new external dependency is introduced.

### Success Criteria

| ID | Измеримый результат | Проверка / источник | Type |
|---|---|---|---|
| SC-001 | `bin/loop --help`, `bin/loop <project> --status` and direct `loop/loop.sh --help` resolve through Python runner and exit 0. | `bin/pytest loop/tests/test_runner_cli.py -q` | outcome |
| SC-002 | One fake public loop turn reaches session and terminal decision with no shell function sourcing. | `bin/pytest loop/tests/test_runner_e2e.py -q` | outcome |
| SC-003 | Claude/DSH/Codex runtime-specific command and failure behavior remains green. | existing adapter/dispatch/session tests plus new runner tests | outcome |
| SC-004 | `rg` finds zero production callers of removed shell orchestration symbols and zero `source loop/loop.sh` in active tests/instructions. | replacement `rg` controls in purge step | outcome |
| SC-005 | Timeout, interrupt, retry cap, model substitution, missing binary, lock contention and fail-closed `check-after` have executable evidence. | TM-086-01…TM-086-10 | outcome |
| SC-006 | No second supervisor path remains; `loop.sh` is a delegation shim under 30 non-comment lines. | `wc -l loop/loop.sh` + content/entrypoint test | outcome |

### Assumptions

- Python 3.12 and stdlib `argparse`, `subprocess`, `fcntl`, `signal`, `dataclasses`, `pathlib` are available in the hub runtime.
- Linux/POSIX locking semantics are an existing runtime constraint because current loop uses `flock`; Windows support is not introduced by this epic.
- `T-HUB-079` supplies the lifecycle/terminal telemetry contract before this runner cutover is implemented; this plan does not redefine it.
- Existing `RuntimeAdapter` and `session_resilience` contracts are treated as behavior baselines; any required signature extension must have a compatibility test.
- Product state remains owned by `PROJECT_ROOT/memory-bank/**`; hub runtime state remains under `HUB_ROOT/runtime/<slug>/epic/`.
- Operator-facing compatibility is more important than preserving internal shell function names; source-based callers are migrated in-epic.

### Clarifications

- Session: 2026-09-08 / user + assistant discussion.
- Решение: Python становится canonical supervisor; `bin/loop` и `loop.sh` сохраняются как public/delegating entrypoints; no behavior expansion.
- Phase 0 result: taxonomy clear from the preceding decision and current as-built inventory; no separate clarify artifact.

### [НУЖНО УТОЧНИТЬ]

- `n/a` — no blocking clarification remains for the proposed vertical slice.

## AC

1. `python3 -m loop.runner --help` and `loop/loop.sh --help` return 0 and show the same operator-relevant options.
2. `bin/loop` resolves a product root exactly as before, then delegates to one Python entrypoint; no shell runner logic is executed after delegation.
3. `--status`, `--dag-generate`, `--phase GAP_FANOUT` and `doctor` paths remain non-session commands and preserve their existing output/exit contracts.
4. A normal fake Claude/DSH/Codex session goes through existing adapter and session-resilience contracts, writes the expected log, and returns the runtime exit code to `record-session`.
5. A transient abort re-prepares context before retry, respects configured retry cap/backoff, and resumes outer prepare when cap is reached.
6. A permanent failure, model substitution, missing runtime binary, invalid config or DSH profile failure halts non-zero without provider fallback.
7. `SIGINT`/`SIGTERM` does not cause an outer retry; owned `runner.json` is cleaned only by the owning pid/session identity.
8. `check-after` action selection is delegated to `halt_logic.decide_after_action`, and `NEED_HUMAN`/fail-closed halt is not converted into blind continue.
9. Existing runtime state paths, session log retention, `last-session.json`, trace/incident artifacts and checkpoint ownership remain unchanged.
10. Public behavior tests do not source `loop.sh`, invoke shell functions, or assert implementation text as the only evidence.
11. Active docs and instruction surfaces no longer present shell orchestration as the canonical machine path.
12. The final purge scan has no A/B/C/I leftovers and the runner shim has exactly one production caller path.

### AC− (brownfield replace / cutover)

1. Нет второго исполняемого supervisor-а с отдельным outer `while`, retry policy или `check-after` decision tree.
2. Нет `source loop/loop.sh` в production instructions/tests; shell functions не являются API.
3. Нет `python3 -c`/shell text extraction для machine JSON, runtime result или owner state.
4. Нет `try new except old`, automatic fallback Python → shell или unknown runtime → Claude.
5. Misconfiguration, missing binary, invalid adapter, lock contention and malformed result produce explicit non-zero/fail-closed outcome.
6. Нет active instruction surface, которая требует чтения/ручного редактирования runner files вместо public status/doctor/CLI.
7. Нет obsolete tests, которые вынуждают вернуть удалённый shell contract ради green suite.
8. Нет изменения state/telemetry semantics, замаскированного под migration; contract regressions are failures, not accepted migration differences.

## Техника / архитектура (HOW)

### Canonical module boundary

Новый пакет `loop/runner/` разделяет orchestration responsibilities, но сохраняет один production composition root:

| Модуль | Ответственность | Публичный контракт |
|---|---|---|
| `loop/runner/__main__.py` | `python -m loop.runner` adapter | `raise SystemExit(main())` |
| `loop/runner/cli.py` | argparse, positional compatibility, command routing | `main(argv: Sequence[str] | None) -> int`, `parse_cli(argv) -> CliArgs` |
| `loop/runner/config.py` | path/env/runtime config resolution | `RunnerConfig.from_environment(...) -> RunnerConfig` |
| `loop/runner/ownership.py` | POSIX lock, owner publish/remove, signal-safe cleanup | `RunnerLease` context manager |
| `loop/runner/session.py` | adapter command + session wrapper invocation + stream filter wiring | `SessionInvoker.invoke(request) -> SessionResult` |
| `loop/runner/orchestrator.py` | outer loop state transitions and retry policy | `LoopRunner.run() -> RunOutcome` |
| `loop/runner/output.py` | human summaries and structured diagnostics | pure formatters; no state mutation |
| `loop/loop.sh` | compatibility delegation only | `exec python3 -m loop.runner "$@"` |

### Typed contracts

```python
@dataclass(frozen=True)
class RunnerConfig:
    hub_root: Path
    project_root: Path
    state_dir: Path
    runtime: RuntimeConfig
    permission_mode: str
    headless: bool
    interactive: bool
    verbose: bool
    cli_model: str | None
    epic_spec: str | None
    epic_id: str | None
    mode: str | None
    extra_args: tuple[str, ...]


@dataclass(frozen=True)
class SessionRequest:
    session_id: str
    prompt_file: Path
    runtime_id: str
    phase: str
    model: str | None
    mode: Literal["headless", "interactive"]
    log_file: Path
    timeout_sec: int
    kill_grace_sec: int
    heartbeat_sec: int | None
    idle_timeout_sec: int | None
    permission_mode: str
    extra_args: tuple[str, ...]
    project_root: Path
    hub_root: Path
    runtime_extras: Mapping[str, Any]


@dataclass(frozen=True)
class SessionResult:
    exit_code: int
    runtime_id: str
    log_file: Path
    interrupted: bool = False


class RunAction(StrEnum):
    CONTINUE = "continue"
    COMPLETE = "complete"
    HALT = "halt"


@dataclass(frozen=True)
class RunOutcome:
    action: RunAction
    exit_code: int
    reason: str | None = None
```

`RuntimeConfig`, `RunnerOwner`, `RuntimeAdapter`, `SessionContext` и существующие schema/state types переиспользуются; не создавать вторые версии этих contracts.

### Data flow

```text
operator
  -> bin/loop (project/runtime shorthand)
  -> loop/loop.sh (compatibility exec shim)
  -> loop.runner.cli
  -> RunnerConfig + RunnerLease
  -> context_loop.prepare_session()
  -> SessionInvoker -> runtime registry/adapter -> session_resilience
  -> record_abort()/check_after()
  -> halt_logic.decide_after_action()
  -> continue | complete | halt + runtime evidence
```

Все provider process calls остаются bounded и выполняются через `session_resilience`; все state decisions остаются в `context_loop`/existing reducers. `LoopRunner` только координирует порядок и превращает typed results в следующую action.

### CLI compatibility rules

1. `bin/loop` продолжает определять `PROJECT_ROOT` из explicit path или current directory и `EPIC_RUNTIME` из первого shorthand positional.
2. `loop/loop.sh` больше не должен быть source-able API; прямой запуск делегирует в Python после вычисления hub root.
3. Python parser принимает нормализованный argv после shell launcher; positional interpretation переносится в `cli.py`, чтобы direct module invocation и wrapper invocation имели один parser.
4. `doctor` и `dashboard` special routes из `bin/loop` либо остаются direct `context_loop` commands, либо передаются в `loop.runner.cli`; в обоих случаях help/status не стартуют autonomous loop.
5. Exit code `0` означает clean command/continue completion as currently exposed; `3` remains internal terminal/continue marker only where existing `context_loop` contract requires it; user-facing halt remains non-zero.

### Session invocation rules

- Adapter builds argv; runner adds only cross-runtime concerns: project visibility, permission/model args, session wrapper bounds, expected model, stdin-file and stream-filter selection.
- Stream filter is selected by runtime registry/capability or explicit adapter metadata; runner must not reintroduce a `claude/dsh/codex` outer branch. If current filter names are not registry metadata, add a typed `stream_filter` capability/metadata field to the adapter contract and cover it.
- DSH binary/profile installation is a runtime adapter concern exposed through a typed preparation result; missing executable or installer failure returns a structured fatal result.
- Codex stdin prompt and product cwd remain adapter/session request behavior; no shell-specific `mapfile`/NUL transport is retained.
- Interactive mode must preserve terminal stdin behavior; headless mode must preserve log/stream output behavior.

### Outer-loop rules

1. Resolve runtime config and acquire lock once per runner process.
2. Arm explicit epic before first prepare; an already complete epic returns clean completion.
3. On each iteration prune old logs, call `prepare_session`, handle complete/halt/degraded results, then invoke one bounded session.
4. Call `record_abort` for every non-interrupt session result; classify retryability from its structured response.
5. For transient retry, sleep only configured backoff, re-run prepare, compare step/epic completion and avoid stale retry against a completed epic.
6. After clean session call `check_after(fingerprint_before)` and `decide_after_action`; never infer action from raw process exit alone.
7. On `continue`, start a new outer iteration; on `complete`, perform existing roadmap/DAG continuation rules; on `halt`, run existing incident/Tier-1 policy and exit fail-closed.

## Инвентарь файлов и ответственности

### Create

| File | Responsibility |
|---|---|
| `loop/runner/__init__.py` | package boundary and stable import surface for `main`, `LoopRunner`, contracts |
| `loop/runner/__main__.py` | module execution entrypoint |
| `loop/runner/cli.py` | parser, path normalization, command routing and exit mapping |
| `loop/runner/config.py` | Python env/config bootstrap and `RunnerConfig` construction |
| `loop/runner/ownership.py` | lock/owner/signal lifecycle |
| `loop/runner/session.py` | session request construction, adapter dispatch, wrapper/filter process wiring |
| `loop/runner/orchestrator.py` | `LoopRunner` state machine and transient retry outer loop |
| `loop/runner/output.py` | prepare/after/arm/action summaries and safe JSON diagnostics |
| `loop/tests/test_runner_cli.py` | parser, public entrypoints, non-session command parity |
| `loop/tests/test_runner_ownership.py` | lock contention, owner cleanup, interrupt semantics |
| `loop/tests/test_runner_session.py` | adapter/session wrapper/filter/runtime failure behavior |
| `loop/tests/test_runner_orchestrator.py` | fake collaborator lifecycle, retry/action matrix |
| `loop/tests/test_runner_e2e.py` | public `bin/loop`/shim vertical slice with fixtures |

### Modify

| File | Required change |
|---|---|
| `loop/loop.sh` | replace 1172-line runner with compatibility exec shim; no callable orchestration functions |
| `bin/loop` | preserve project/runtime shorthand while delegating only to canonical Python path; remove special direct path only if duplicated by Python CLI, with parity tests |
| `loop/runtime_adapters/base.py` | add only typed provider metadata needed to select cwd/stdin/filter; do not add provider branching to runner |
| `loop/runtime_adapters/common.py` | expose a stable adapter/session metadata factory if required by `SessionInvoker` |
| `loop/runtime_adapters/dsh.py` | move/retain DSH resolver/profile preparation behind adapter-owned typed method; preserve `DSH_BIN`, resolver and npx argv semantics |
| `loop/runtime/dispatch.py` | reuse or narrow its command-building API so the runner does not shell out to JSON argv; preserve existing CLI for external callers |
| `harness/hooks/session_resilience.py` | add only a tested callable invocation/result adapter if subprocess CLI is no longer needed; preserve CLI and all timeout/log classification behavior |
| `harness/hooks/_lib.py` | reuse `load_project_env`, `resolve_runtime_config`, owner helpers; add no second env/owner schema |
| `loop/tests/test_loop_dsh_dispatch.py` | replace `source loop.sh` calls with public Python/session API and public entrypoint tests |
| `loop/tests/test_dsh_e2e_smoke.py` | invoke canonical runner and keep DSH fixture evidence |
| `loop/tests/test_loop_shell_halt_parity.py` | rename/reframe as Python halt/action parity tests; remove source-text shell assertions |
| `loop/tests/test_session_boundary.py` | verify boundary through Python runner/checkpoint behavior, not shell text |
| `loop/tests/test_context_loop.py` | move remaining shell orchestration assertions to runner tests; retain context domain tests |
| `loop/tests/test_loop_slash_commands.py` | assert one canonical module/compatibility path and no obsolete standalone runners |
| `README.md`, `loop/README.md`, `loop/WORKFLOW.md`, `LOOP-RUNTIMES.md` | teach `bin/loop` and Python module; label shell direct path compatibility-only |
| `docs/runbooks/codex-loop-pilot.md`, `docs/runbooks/dsh-loop-pilot.md` | update runtime invocation and troubleshooting to Python supervisor boundary |
| `harness/instructions/epic-loop.md`, `loop-state.md`, `program-loop.md` | replace shell-as-runner prose and source/function guidance |
| `harness/claude/commands/epic-run.md`, `epic-status.md`, `loop-run.md`, `program-run.md` | point commands to canonical CLI/public launcher without starting status commands accidentally |
| active role/rule surfaces found by the final I scan | rewrite only references that teach shell orchestration as machine SoT; historical/archive references are excluded explicitly |
| `memory-bank/architecture/overview.md`, `services.md`, `data-flow.md`, `services-dataflow.md`, `containers.md`, `workers.md`, `dsh-runtime.md` | refresh as-built service/flow descriptions after implementation; preserve state/runtime contracts |
| `memory-bank/tasks.md`, `memory-bank/back/roadmap/queue.yaml` | register epic and canonical plan queue row |

### Do not modify

- `memory-bank/activeContext.md` during PLAN; implementation will create its own Handoff through FINISH workflow.
- Product repositories outside this hub.
- Existing runtime state under `runtime/**`.
- Historical `memory-bank/archive/**`, completed QA/audit artifacts and immutable evidence, except links/scan exclusions in plan.
- Provider command semantics and existing adapter test fixtures unless a test must be moved from shell API to public Python API.

## Eng review spine

### Data flow

```text
[CLI argv/env]
      | normalize + validate
      v
[RunnerConfig + RunnerLease]
      | prepare context
      v
[context_loop.prepare_session]
      | SessionRequest
      v
[RuntimeAdapter + session_resilience]
      | SessionResult + log
      v
[record_abort/check_after]
      | typed action
      v
[continue / complete / halt]
```

Синхронные границы: CLI/config/prepare/record/check-after вызовы; bounded subprocess boundary: runtime process through `session_resilience`; file IPC: product `memory-bank` and hub `runtime`. No new async queue or network service.

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|---|---|---|---|---|
| CLI → config | missing `PROJECT_ROOT` or invalid product path | parser/config validation | usage/error, non-zero before lock/session | TM-086-01 |
| config → runtime | invalid runtime config or unsupported runtime | `RuntimeConfigError` / registry exception | fail-closed diagnostic, no Claude fallback | TM-086-02 |
| ownership | second runner on same checkout | non-blocking `fcntl.flock` | exit 1, preserve active owner | TM-086-03 |
| ownership cleanup | stale/foreign owner file | pid/session identity mismatch | do not delete foreign owner; report status | TM-086-04 |
| signal | Ctrl+C/TERM during session | signal handler + session result | terminate owned child, exit 130/143 policy, no outer retry | TM-086-05 |
| adapter | DSH/Codex binary or profile missing | adapter preparation result / `FileNotFoundError` | explicit non-zero halt; no provider substitution | TM-086-06 |
| session | timeout/idle timeout | session resilience bounded result | record transient outcome, reprepare/retry within cap | TM-086-07 |
| session | model substitution/auth/permanent provider failure | session log classifier | permanent fail-closed halt, no retry | TM-086-08 |
| record-session | transient abort after context advanced | structured retry response + reprepare | skip stale retry if epic completed; otherwise retry current cursor | TM-086-09 |
| check-after | NEED_HUMAN/fingerprint conflict/incomplete gate | `decide_after_action` and check-after result | halt with reason; no blind continue | TM-086-10 |
| output | malformed JSON/diagnostic rendering | typed parse exception | preserve raw bounded diagnostic and non-zero; never default runtime | TM-086-11 |
| docs/entrypoint | stale instruction points to shell function | final `rg` instruction scan | purge/rewrite before QA PASS | TM-086-12 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|---|---:|---|
| Data flow complete | 5 | All current lifecycle hops are mapped; implementation must preserve file/process boundaries. |
| Failure coverage | 5 | Matrix covers lock, signal, provider, retry, check-after and instruction drift. |
| Testability | 5 | Composition root uses fake context/session collaborators; public smoke covers real entrypoint. |

## Replacement / sunset (brownfield)

Policy default: `delete in-epic` for shell orchestration symbols and old instruction contract. Public launcher files are rewritten as delegation shims in-epic; they are not an alternate implementation.

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
|---|---|---|
| `loop/loop.sh:ensure_dsh_profiles` | `loop/runner/config.py` + DSH adapter preparation | delete in-epic |
| `loop/loop.sh:configure_runtime_env` | `RunnerConfig.from_environment` and runtime preparation | delete in-epic |
| `loop/loop.sh:find_claude` | adapter/binary resolver boundary | delete in-epic |
| `loop/loop.sh:is_epic_spec` and shell positional parser | `loop/runner/cli.py` parser | delete in-epic |
| `loop/loop.sh:_cleanup_runner_owner` | `RunnerLease.__exit__` / signal-safe ownership | delete in-epic |
| `loop/loop.sh:run_claude_session` | `SessionInvoker.invoke` + Claude adapter | delete in-epic |
| `loop/loop.sh:resolve_dsh_bin` | DSH adapter/runtime resolver | delete in-epic |
| `loop/loop.sh:run_dsh_session` | `SessionInvoker.invoke` + DSH adapter | delete in-epic |
| `loop/loop.sh:run_agent_session` | `SessionInvoker` provider-neutral invocation | delete in-epic |
| `loop/loop.sh:_print_prepare_summary` / `_apply_prepare_session_vars` | typed output/config projections | delete in-epic |
| `loop/loop.sh:_run_context_prepare` / `_reprepare_for_transient_retry` | `LoopRunner.prepare` / retry method | delete in-epic |
| `loop/loop.sh` outer `while true` and action branches | `loop/runner/orchestrator.py:LoopRunner.run` | delete in-epic |
| inline Python heredocs and repeated `python3 -c` JSON parsers in `loop.sh` | direct Python imports and typed JSON parsing | delete in-epic |
| shell-source-only cases in `test_loop_dsh_dispatch.py` and `test_loop_shell_halt_parity.py` | public/API behavior tests | rewrite or delete in-epic |

### B. Entrypoints / deploy

| Устаревает (entrypoint) | Замена | Policy |
|---|---|---|
| `loop/loop.sh` as full supervisor | same path as `exec` compatibility shim to `python3 -m loop.runner` | rewrite in-epic; no alternate runner |
| `bin/loop` → shell full runner assumption | `bin/loop` → compatibility launcher → Python composition root | rewrite in-epic |
| direct `source loop/loop.sh` test/operator API | `python3 -m loop.runner` or public `bin/loop` | delete in-epic |
| Make targets that describe shell internals | same operator target, implementation-neutral | rewrite in-epic |

### C. Fallbacks / soft-fail

| Устаревает (pattern) | Замена (fail-closed) | Policy |
|---|---|---|
| `python3 -c ... 2>/dev/null || true` env/bootstrap path | `load_project_env` with explicit diagnostics and config validation | delete in-epic |
| `echo JSON | python3 -c ... || echo raw` action parsing | typed result parser; raw bounded diagnostic only on parse error | delete in-epic |
| shell branch that silently defaults runtime/command when dispatch data is empty | `InvalidRuntimeConfig`/`SessionResult` fatal outcome | delete in-epic |
| any Python-runner exception that invokes `loop.sh` fallback | non-zero fail-closed error with runner/session diagnostic | delete in-epic |
| DSH missing binary fallback to Claude | explicit exit 127/structured halt | delete in-epic |

### I. Instruction surfaces

| Устаревает (surface) | Замена | Policy |
|---|---|---|
| `README.md`, `loop/README.md`, `loop/WORKFLOW.md`, `LOOP-RUNTIMES.md` describing `loop.sh` as implementation runner | describe `bin/loop` public launcher and Python canonical supervisor; direct shell path compatibility-only | rewrite in-epic |
| `harness/instructions/{epic-loop,loop-state,program-loop}.md` | operator contract through public CLI/status/doctor | rewrite in-epic |
| `harness/claude/commands/{epic-run,epic-status,loop-run,program-run}.md` | commands call one canonical CLI and keep status non-start behavior | rewrite in-epic |
| active `.cursor/rules/**`, `harness/cursor/rules/**` runner references | remove source/function/implementation claims; retain stable public command and state contract | rewrite in-epic |
| `docs/runbooks/{codex-loop-pilot,dsh-loop-pilot}.md` | runtime-specific usage through adapter-backed Python supervisor | rewrite in-epic |
| architecture service/data-flow docs | as-built Python supervisor + shell shim topology | rewrite in-epic |

Historical archive/audit/QA references are not active instruction surfaces; the purge scan must list their exclusions explicitly and must not use them to hide live production callers.

## QA consumes (test plan)

### Scope under test

- Epic/surfaces: `bin/loop`, `loop/loop.sh`, `loop/runner/**`, runtime adapters/dispatch integration, session resilience integration, runner state/lock, active CLI/instruction docs.
- Out of scope for QA: provider service availability, product repository business tests, historical archive prose, new runtime capability, parallel DAG execution.

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|---|---|---|---|---|---|
| TM-086-01 | P0 | missing/invalid project root and CLI parity | `bin/pytest loop/tests/test_runner_cli.py -k 'project or help or parse' -q` | non-zero for invalid input; 0 for help; no session process | FR-001/2/3, AC-1/2 |
| TM-086-02 | P0 | registry unknown/invalid runtime | `bin/pytest loop/tests/test_runner_cli.py loop/tests/test_runner_session.py -k 'unknown or invalid' -q` | structured diagnostic, non-zero, no fallback | FR-003/8/9, AC-6 |
| TM-086-03 | P0 | lock contention and owner identity | `bin/pytest loop/tests/test_runner_ownership.py -q` | second runner exits; foreign owner survives; owner cleanup is atomic/owned | FR-005/6, AC-7 |
| TM-086-04 | P0 | fake Claude/DSH/Codex command/session execution | `bin/pytest loop/tests/test_runner_session.py loop/tests/test_runtime_dispatch.py -q` | argv/cwd/profile/stdin/filter/log match baseline; exit code passes through | FR-008/9, AC-4 |
| TM-086-05 | P0 | full public one-turn lifecycle | `bin/pytest loop/tests/test_runner_e2e.py -q` | `bin/loop` reaches Python runner, writes state/log and terminal action | FR-001/10/11, AC-2/4 |
| TM-086-06 | P0 | transient retry and reprepare | `bin/pytest loop/tests/test_runner_orchestrator.py -k 'transient or reprepare or cap' -q` | retry bounded; prepare reruns; stale completed epic not retried | FR-010/11, AC-5 |
| TM-086-07 | P0 | permanent/model/signal/timeout failures | `bin/pytest loop/tests/test_runner_orchestrator.py loop/tests/test_session_resilience_adapter.py -k 'permanent or model or signal or timeout' -q` | fail-closed or bounded retry as policy; interrupt not outer retry | FR-008/10/11, AC-6/7 |
| TM-086-08 | P0 | check-after action parity | `bin/pytest loop/tests/test_runner_orchestrator.py loop/tests/test_context_loop.py -k 'halt or complete or fingerprint or human' -q` | decision goes through `decide_after_action`; no raw rc retry | FR-011, AC-8 |
| TM-086-09 | P1 | non-session commands | `bin/pytest loop/tests/test_runner_cli.py -k 'status or doctor or dag' -q` | status/doctor/DAG commands do not start agent session | FR-002/7/11, AC-3 |
| TM-086-10 | P1 | public shell shim and syntax | `bash -n bin/loop loop/loop.sh && bin/pytest loop/tests/test_loop_slash_commands.py -q` | syntax pass; shim delegates once; no orchestration symbols | FR-013/14, AC-1/12 |
| TM-086-11 | P1 | sunset/instruction enforcement | `rg` commands from final purge inventory | every A/B/C/I row pass; no source-based active caller | FR-014/15, AC−-1…7 |
| TM-086-12 | P1 | targeted loop regression | `bin/pytest loop/tests/test_loop_dsh_dispatch.py loop/tests/test_dsh_e2e_smoke.py loop/tests/test_session_boundary.py -q` | existing behavior remains green after tests are rewritten | FR-009/12/14, AC-4/9 |

### Regression notes

- Run tests from repository root through `bin/pytest`; do not use bare `pytest`.
- Parent session owns test execution; no subagent runs frontend tests (not applicable to this backend plan).
- Existing dirty worktree changes are not part of this plan; implementation must preserve them and isolate runner migration commits/steps by diff.
- A green test suite is insufficient if `rg` still finds live shell orchestration callers or instructions; TM-086-11 is mandatory.
- Full suite is BACK QA scope after targeted implementation checks; implementation work should run only targeted runner/runtime tests.

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| CLARIFY / Product probe | L3+ one of done | done | §Product probe; Phase 0 taxonomy clear from accepted prior decision |
| Eng review spine | L2+ | done | §Eng review spine data flow, failure matrix and self-check |
| §0.11 counterparts | if external refs in HOW | done | Existing `context_loop`, runtime adapter, session resilience and state contracts listed in file map/refs |
| Delivery closure | P0 boundary | done | §Delivery closure has public caller, success/failure enforcement and independent test |
| CREATIVE | if flagged | n/a | No UI/design/content creative surface |
| QA consumes draft | L2+ | done | §QA consumes has 12 TM rows, including 8 P0 rows |
| Plan review batch | L2+ | done | §Plan review batch log records product/eng decisions and deferred polish |

No Required row is `pending`.

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|---|---|---|---|
| Product | Existing user decision is a maintainability/cutover request; public invocation must remain unchanged; one vertical slice is sufficient. | Optional output formatting polish → owner: implementation; next: only if core acceptance is green. | No CRITICAL product ambiguity. |
| Eng | Reuse context/state/runtime/session contracts; introduce Python composition root; keep shell files as delegation shims; hard-depend on lifecycle contract. | Historical documentation cleanup beyond active surfaces → owner: follow-up docs maintenance only if purge scan finds non-active drift. | CRITICAL guard: no second supervisor path, no silent fallback, no state semantics change. |

## До DECOMPOSE (черновик нарезки)

Ожидается последовательная vertical-slice нарезка; количество `sNN` advisory, coverage важнее числа.

### Stage 1 — contract characterization and runner seams

- Add public CLI/entrypoint characterization tests for current help/status/arm/prepare/session/terminal behavior.
- Define typed `RunnerConfig`, `SessionRequest`, `SessionResult`, `RunAction` and fake collaborators.
- Add tests for lock ownership and signal/exit policy before deleting shell functions.

### Stage 2 — Python composition root and configuration/ownership

- Implement `loop/runner/cli.py`, `config.py`, `ownership.py`, module entrypoint and stable imports.
- Reuse `load_project_env`, `resolve_runtime_config`, `RunnerOwner`, `write_runner_owner`, `remove_runner_owner_if_owned`.
- Prove project/hub/state path and owner JSON parity.

### Stage 3 — provider-neutral session invocation

- Implement `SessionInvoker` using registry/adapters and existing session resilience boundary.
- Preserve Claude/DSH/Codex cwd, argv, profiles, stdin, filters, timeout, heartbeat, idle and log behavior.
- Add provider fixture tests and fail-closed missing binary/config cases.

### Stage 4 — outer orchestration migration

- Implement `LoopRunner` for arm, prepare, bounded session, record, reprepare, action decision, incidents and DAG/roadmap continuation.
- Use direct typed Python calls where public functions exist; keep CLI subprocess only where an existing process boundary is contractually required.
- Add fake-collaborator tests for clean, transient, permanent, interrupt, complete, NEED_HUMAN and fingerprint-stall paths.

### Stage 5 — cutover and compatibility shims

- Replace `loop/loop.sh` with a minimal exec shim and adjust `bin/loop` to one canonical delegation path.
- Remove shell orchestration functions, heredocs and inline JSON parsing.
- Rewrite shell-source tests into public runner/API tests; no obsolete source API remains.

### Stage 6 — active instruction/docs migration

- Update operator docs, commands, rules/instructions and architecture service/data-flow descriptions.
- Ensure direct shell mention is compatibility-only and no active surface teaches source/function API.
- Keep public `bin/loop` examples and Python module maintainer command consistent.

### Stage 7 — final legacy purge and QA evidence

- Create final `*-legacy-fallback-purge` step with complete A/B/C/I `sunset_inventory` and executable `grep_control` rows.
- Run targeted runner suite, shell syntax/public smoke, full BACK QA suite and independent sunset scan.
- Record `wire_complete`, `sot_enforce_scan`, actual outputs and remaining surfaces; no `legacy_surfaces_remaining` without follow-up epic ID.

### Required decompose coverage

The decompose index must map every FR/AC/AC−/TM row to a measurable step and include the machine-boundary ladder:

`add typed runner → wire public caller → enforce Python-only path → legacy-fallback-purge`.

The final purge shard must include each A/B/C/I row from this plan, including obsolete shell-source tests and active instruction references. It must not delete public shims until their delegation tests are green.

## Appetite

| Поле | Значение | Описание |
|---|---|---|
| `timebox_days` | `5` | Implementation + targeted verification; full BACK QA follows normal workflow. |
| `cut_list` | `['unified pretty output renderer', 'historical archive prose rewrite', 'new provider capability', 'parallel DAG execution']` | These do not justify leaving a second supervisor path or skipping purge/evidence. |

## Следующий режим

→ **BACK DECOMPOSE T-HUB-086-python-loop-supervisor-cutover** после queue reconcile. Затем ANALYZE/IMPLEMENT по обычной BACK transition chain; не `BACK ROADMAP MERGE`.

### CREATIVE need

**нет**
