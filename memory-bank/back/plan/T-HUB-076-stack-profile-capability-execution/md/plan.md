# [T-HUB-076 | stack-profile-capability-execution] PLAN

**Дата:** 2026-09-07  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear: пользователь явно потребовал подключить исполнение после T-HUB-075; исходный эпик уже зафиксировал profile API, безопасные границы и то, что lifecycle execution вынесен в follow-up.  
**Prompt:** [md/prompt.md](prompt.md) — outcome SoT, не HOW.  
**Deps:** hard T-HUB-075 (QA PASS и сохранённый contract `stack-capability-resolution/v1`); soft T-HUB-054 (общий contract runner/timeout).  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns (Eng review).  
**Источник:** пользовательское решение «подключаем исполнение»; T-HUB-075 FR-014 / cut-list; `loop/stack_profiles/*`; `loop/context_loop.py`; `harness/hooks/epic_yaml.py`.

→ После DECOMPOSE единственный трекер — [yaml/decompose-index.yaml](../yaml/decompose-index.yaml) / [md/decompose-index.md](decompose-index.md); sNN-checkbox здесь намеренно не дублируются.

## Контекст

T-HUB-075 уже умеет строго прочитать корневой `dev-hub.project.yaml`, выбрать явный target, сформировать `CapabilityResolution` и вернуть безопасные `argv: list[str]`, `cwd`, requirements и `timeout_seconds` для Python, Rust и JavaScript. Его публичный резолвер не выполняет команду — это было правильной границей первого эпика. Однако действующие BACK/INTEG правила и finish-валидатор продолжают описывать проверку как Python-ориентированную строку shell-команды, а `loop/context_loop.py check-after` не запускает profile capability.

Проблема не сводится к замене слова `pytest` на `cargo` или `npm`. Такая замена оставляет три дыры:

1. Резолвер остаётся мёртвым для runtime: production caller есть только в JSON CLI, но не в workflow phase.
2. `tests:` в implement YAML подтверждается строковыми prefix-правилами из `harness/hooks/test_run_canon.py` и `harness/hooks/tests_format.py`; Rust/JS result нельзя доказать как typed evidence.
3. Промпты требуют команды, которые либо не соответствуют profile target, либо не имеют единого execution result; это Kind I drift относительно нового machine boundary.

Эпик вводит один проверяемый путь: **явно объявленный capability check в decompose shard → typed resolver → argv-only executor → typed evidence sidecar → check-after / finish gate → workflow instruction**. Он не делает workflow произвольным shell runner и не меняет hub self-test.

### Границы терминов

| Термин | Значение | Не является |
|---|---|---|
| Hub self-test | Проверка самого `dev-hub`: `bin/pytest`, `loop/tests`, `harness/hooks/tests`, repository-local frontend checks. | Managed-project capability.
| Managed project | Project root, в котором лежит strict `dev-hub.project.yaml`; profile/target принадлежат этому root. | Рабочая копия hub по умолчанию.
| Capability declaration | Typed request из decompose shard: capability + **обязательный** named target + selector только для `test.targeted`. | Строка shell, argv или env из YAML.
| Capability execution | Один вызов resolver-а и точное выполнение его готовых `argv` при его `cwd` и timeout. | `bash -c`, `shlex.split`, повторная интерполяция selector-а.
| Evidence | JSON sidecar с request fingerprint, resolution summary и результатом процесса; finish валидирует его. | Текст «tests passed» в YAML.

## Technology axiom (replace-not-wrap)

As-built нужен только для inventory того, что удалить или сузить. Новый контракт проектируется от profile resolution, а не как расширение allowlist строковых команд.

| Выбор | Единственный machine input / SoT | FORBIDDEN после эпика |
|---|---|---|
| Проверка managed project | `CapabilityCheckSpec` в decompose shard | shell command, `cwd`, `argv`, `env` или profile в implement evidence.
| Исполнение | успешный `CapabilityResolution` → точные `argv`, `cwd`, `timeout_seconds` | shell=True, `bash -c`, `shlex.split`, command re-render, fallback на pytest/npm/cargo.
| Факт выполнения | `stack-capability-execution/v1` sidecar с fingerprint request/result | prose PASS, подмена результата вручную, проверка только наличия CLI.
| Phase gate | `check_after` запускает объявленные checks и fail-closed блокирует дальнейший success path | optional execution, «agent может запустить», default target без декларации target.
| Hub tests | отдельный `hub_tests` / legacy `tests` contract только для hub surfaces | миграция `bin/pytest` через profile или признание Python suite полной QA managed monorepo.

### Зафиксированные решения

1. Эпик использует только шесть capabilities T-HUB-075: `format.check`, `lint`, `typecheck`, `test.targeted`, `test.full`, `build`. Новые `test.e2e`, `run`, `migrate`, `deploy` не добавляются.
2. Для phase-executed check `target` обязателен даже если manifest содержит `default_target`. Default target безопасен для direct resolver API, но не является достаточным audit trail для workflow/QA.
3. `selector` допускается только для `test.targeted`, передаётся resolver-у один раз и остаётся одним argv atom. Executor не нормализует и не split-ит selector.
4. Managed check наследует окружение процесса, но request/decompose/CLI не принимают supplied environment, executable path или arbitrary timeout. Runtime использует именно resolver timeout.
5. Execution result не сохраняет stdout/stderr как доказательство успеха и не включает секреты в YAML. Он хранит exit code, duration, byte counts, truncation flag, stable diagnostic и относительный bounded log reference, если безопасный log создан.
6. Phase runner исполняет только checks текущего armed step и только после того, как phase может прочитать strict manifest. Отсутствующий manifest, invalid declaration или failed command — HALT с typed diagnostic; не fallback к hub test string.

## Продуктовая спека (WHAT)

### Product probe

| # | Probe | Decision / impact |
|---|---|---|
| 1 | Reframe | Нужна не таблица команд трёх языков, а проверяемый quality-port между workflow intent и безопасным target subprocess. |
| 2 | Narrowest wedge | Выполнять только шесть уже разрешённых verification capabilities из explicit decompose declaration; никакого generic `run`. |
| 3 | Pre-mortem | Наиболее вероятные поломки — shell injection через selector, ложный PASS по prose и QA только Python target. Каждый устранён typed request, sidecar и mandatory target. |
| 4 | Distribution / adoption | Автор BACK/INTEG step указывает `capability_checks`; `check-after` создаёт evidence; правила обучают новый путь после того, как gate уже работает. |
| 5 | Technical leverage | Использовать готовый `CapabilityResolution`; не дублировать registry logic и не переиспользовать `runtime.dispatch` (он запускает AI runtime, а не quality checks). |
| 6 | Appetite | Четыре дня. Сначала cut: profile-version floors, E2E vocabulary, remote/custom profiles, arbitrary command migration и автоматическое исправление failures. |

### User Stories

| # | Story | P | Independent Test |
|---|---|---|---|
| US-001 | Как автор workflow step, я объявляю Rust/Python/JS verification intent, а не shell command, чтобы runtime применил только registry-owned argv. | P0 | Temporary monorepo: three explicit targets yield exact executed argv/cwd and status PASS. |
| US-002 | Как QA owner monorepo, я вижу какой named target и capability действительно завершились, чтобы Python default не маскировал Rust/JS coverage. | P0 | Two-target fixture without declaration target HALT; explicit two evidence records both required. |
| US-003 | Как оператор, я получаю JSON result и stable non-zero outcome при invalid manifest, spawn error, timeout или non-zero command. | P0 | CLI/API matrix asserts JSON schema, diagnostic and no fallback subprocess. |
| US-004 | Как maintainер hub, я сохраняю `bin/pytest` для тестов hub, не превращая собственный Python suite в profile policy внешнего проекта. | P1 | Existing hub test-format fixtures still validate; managed capability evidence validates separately. |
| US-005 | Как автор правила, я даю агенту только исполнимый machine path, поэтому workflow text не требует hardcoded pytest/cargo/npm commands. | P1 | Instruction inventory shows no generic managed-project command literals; runtime check-after consumes declaration. |

### Acceptance Scenarios

#### US-001 — successful resolved execution

- **Given:** temporary workspace has strict manifest with `py`, `rs`, `web` targets and corresponding minimal executable fakes/lockfiles.
- **When:** phase runner receives three explicit `CapabilityCheckSpec(... capability="test.full")` declarations.
- **Then:** it calls resolver once per declaration and executes exactly resolver argv/cwd: Python, `cargo test --all-targets`, and selected JS manager `run test`; each emits typed success evidence.

#### US-002 — target is not implicit in workflow evidence

- **Given:** managed manifest has a `default_target` and two named targets.
- **When:** a decompose `capability_checks` row omits `target`.
- **Then:** decompose validation / check-after fails `capability_target_required`; neither target command is spawned.

#### US-003 — invalid or failing execution cannot become a green phase

- **Given:** resolver emits `js_package_manager_ambiguous`, or the resolved executable is absent, times out, or exits non-zero.
- **When:** CLI or phase runner performs the declared check.
- **Then:** JSON evidence has empty/safe result as appropriate, stable diagnostic/status, non-zero exit; `check-after` HALTs and no finish proof is accepted.

#### US-004 — hub boundary remains intact

- **Given:** a hub implementation shard has no managed `dev-hub.project.yaml` and contains a hub test command.
- **When:** finish validation runs.
- **Then:** the existing hub test canon remains valid; resolver/executor is not invoked and no profile is inferred.

### Functional Requirements

- **FR-001:** Add strict typed models for a phase declaration, execution result and persisted evidence. Unknown fields fail; declaration accepts only capability enum, required target and optional selector under existing selector rules.
- **FR-002:** Add a public executor that accepts only project root plus typed request/declaration, calls `resolve_capability()`, and runs only `resolution.argv` with `resolution.cwd`, `timeout_seconds` and `shell=False`.
- **FR-003:** Executor never accepts raw command text, caller argv, cwd override, env override, profile override or timeout override; resolver failure means no subprocess call.
- **FR-004:** Execution emits `stack-capability-execution/v1` JSON with request fingerprint, resolution identity, start/end or duration, exit code/status, bounded output metadata and ordered diagnostics. No output body or secret-bearing environment is embedded in memory-bank YAML.
- **FR-005:** `python -m loop.stack_profiles execute` is JSON-first and exposes the same typed result as API. Exit mapping distinguishes success, configuration/selection failure, unavailable/spawn failure, timeout, and delegated command failure.
- **FR-006:** Extend decompose schema with explicit `capability_checks`; BACK/INTEG phase declarations are valid only with required named targets, allowed capability/selector pairing and no raw process fields.
- **FR-007:** `loop.context_loop.check_after()` finds declared checks for the current armed step, executes them before returning a green continuation, persists evidence under the role/epic/step execution artifact path and HALTs on any failed/missing/stale evidence.
- **FR-008:** Finish/step validation recognises typed managed-project evidence and validates it against the current declaration fingerprint. Hub command evidence remains a separate, explicit contract and remains valid for hub-only work.
- **FR-009:** Update BACK, INTEG and shared workflow instructions so managed project work declares and receives capability checks; instructions no longer prescribe Python-specific generic test commands as the managed-project default.
- **FR-010:** Keep FRONT parent-only test authority. This epic may rewrite its vocabulary from manager literals to “managed frontend capability / approved scenario runner”, but it does not add profile `test.e2e` or execute browser tests through the capability executor.
- **FR-011:** All old generic-string assumptions are removed from validation and instruction surfaces in the same epic. Any remaining raw `tests:` string is labelled hub-only, cannot be used to satisfy a managed declaration, and never triggers a legacy fallback.
- **FR-012:** Direct resolver/doctor behaviour from T-HUB-075, immutable registry vocabulary, JS lockfile policy, target containment and hub self-test runner are unchanged.

### Success Criteria

| ID | Result | Verification | Type |
|---|---|---|---|
| SC-001 | Every bundled profile executes an explicit `test.full` through one executor. | Temporary three-target monorepo exact argv/cwd + exit evidence. | outcome |
| SC-002 | No resolver/validation failure invokes a target subprocess. | Mock spawn asserts zero calls for all diagnostics. | safety |
| SC-003 | Failed, timed-out and non-zero command evidence blocks check-after. | Context-loop integration test asserts HALT/result path. | behavior |
| SC-004 | A managed result cannot be proven by raw shell test prose. | Finish validator rejects string-only proof where declaration exists. | enforce |
| SC-005 | Hub self-tests remain accepted without manifest/profile inference. | Existing formatter/finish regression plus no executor mock call. | regression |
| SC-006 | Active workflow rules do not teach generic `bin/pytest` as managed-project execution. | Scoped Kind I `rg` inventory and instruction tests. | migration |

### Assumptions and clarifications

- T-HUB-075 reaches QA PASS before this epic is implemented; if its resolver contract changes, T-HUB-076 re-plans against the new version rather than adding compatibility parsing.
- A target command can fail for normal product reasons. The executor reports the failure faithfully; it never retries, installs dependencies or repairs source code.
- A phase check may be expensive, but only registry-owned `timeout_seconds` governs it. V1 remains 300 seconds for bundled profiles.
- A project without `dev-hub.project.yaml` is hub/self-test context unless a future adoption epic defines another explicit managed-root transport. This epic does not search parents or children.
- Browser scenario runners, migrations, service startup, package installation, version floors and arbitrary `make` targets are out of scope.

### Clarifications

- Session: 2026-09-07, `BACK PLAN`; no separate Q→A artifact because the requested follow-up is the explicit deferred lifecycle boundary of T-HUB-075.
- Decision: phase declaration requires named target even when direct resolver API may use manifest default.
- Decision: string command evidence is retained only for hub self-tests, not as compatibility fallback for a managed project.

## AC

1. A named Python, Rust or JavaScript target executes each declared capability using only resolver-generated argv/cwd.
2. A workflow phase has a machine-readable declaration and a persisted typed result; neither agent prose nor file presence alone can mark it green.
3. `check-after` enforces the declaration and halts a phase if the resolver, spawn, timeout or command result fails.
4. Finish validation ties evidence to the current step/declaration fingerprint and cannot accept a result from another target, capability or step.
5. Hub self-tests keep their current runner contract and are never resolved as a managed profile.
6. BACK/INTEG/shared rule text distinguishes hub self-test from managed project verification and points to the executable capability path.
7. All three bundled profiles have integration evidence; a monorepo requires explicit QA target rows.
8. No `test.e2e`, arbitrary shell execution, implicit target selection, tool installation or profile extension is smuggled into V1.

### AC−

1. No `shell=True`, `bash -c`, `sh -c`, `eval`, `shlex.split`, string concatenation or caller-supplied argv/cwd/env for a capability subprocess.
2. No fallback from an invalid/missing/failed managed check to `bin/pytest`, `.venv/bin/pytest`, npm, cargo, manifest default target or a raw `tests:` string.
3. No raw command, timeout, profile, package manager, script label or environment field in `capability_checks`.
4. No evidence containing full process output, raw environment or command text invented outside `CapabilityResolution`.
5. No PASS where a declaration omits target, selector violates capability rules, sidecar fingerprint is stale, or declared check was not executed.
6. No change to the six-capability vocabulary, T-HUB-075 lockfile policy or direct hub test wrapper.

## Техника / архитектура (HOW)

### Ownership and layout

| Surface | Owner | New / changed responsibility | Consumers |
|---|---|---|---|
| `loop/stack_profiles/schemas.py` | stack profile boundary | Add strict declaration/execution/evidence models and diagnostics. | executor, CLI, phase runner, validators, tests |
| `loop/stack_profiles/execution.py` | profile boundary | Purely typed execution service; resolve → argv-only subprocess → safe result. | CLI, context loop |
| `loop/stack_profiles/evidence.py` | profile boundary | Request fingerprinting and atomic evidence read/write/path validation. | context loop, finish validator |
| `loop/stack_profiles/__main__.py` | operator CLI | `execute` subcommand JSON/exit mapping. | operator, integration tests |
| `loop/context_loop.py` | phase orchestration | Execute current step declarations during `check_after`, persist/return gate result. | loop runner, check-after CLI |
| `harness/hooks/epic_yaml.py` and `harness/hooks/epic_shard_extra.py` | artifact schema | Parse `capability_checks`, require appropriate evidence at finish. | `epic_resolve`, mb-finish |
| `harness/hooks/tests_format.py` and `harness/hooks/test_run_canon.py` | hub command validation | Narrow names/rules to hub-only command evidence; remove claim that all workflow checks are raw shell strings. | legacy hub shards |
| `harness/cursor/rules/**` plus Claude role-command source | Kind I contract | Instruct declaration/execution/evidence, not hardcoded managed test runner. | Cursor, Claude, Codex materialisation |
| `loop/tests/test_stack_profile_execution*.py` | contract tests | New unit, CLI, phase, finish and migration tests. | CI |

### Typed contracts

The plan deliberately separates a **request** from an **outcome**. A decompose author may express intent, but cannot smuggle execution parameters into that intent.

```yaml
# In an epic-decompose/v1 shard; target is mandatory for workflow execution.
capability_checks:
  - capability: test.targeted
    target: api
    selector: tests/test_health.py::test_ready
  - capability: lint
    target: api
```

Proposed model shape:

```python
class CapabilityCheckSpec(BaseModel):
    capability: CapabilityName
    target: NonEmptyStr
    selector: str | None = None

class CapabilityExecutionResult(BaseModel):
    schema: Literal["stack-capability-execution/v1"]
    ok: bool
    request_fingerprint: str
    target: str
    profile: ProfileName | None
    capability: CapabilityName
    cwd: str | None
    argv: list[str]
    timeout_seconds: int | None
    status: Literal["succeeded", "resolution_failed", "spawn_failed", "timed_out", "failed"]
    exit_code: int | None
    duration_ms: int | None
    stdout_bytes: int
    stderr_bytes: int
    output_truncated: bool
    diagnostics: list[Diagnostic]
```

`argv` in result is copied only from successful resolution and exists for auditability; it is never reparsed. `CapabilityExecutionEvidence` additionally binds `role`, `epic_id`, `step_id`, `decompose_ref`, declaration fingerprint, execution timestamp and result. Evidence write uses an atomic replace into a deterministic relative path, such as `memory-bank/<role>/execution/<epic_id>/<step_id>/capability-<fingerprint>.json`.

### Execution semantics and exit mapping

| Condition | API `status` | CLI exit | `check-after` |
|---|---|---:|---|
| Resolver returns complete `ok=true`; process exits 0 | `succeeded` | 0 | Continue; write evidence |
| Manifest/declaration/target/selector/JS selection diagnostic | `resolution_failed` | 2 | HALT; no spawn |
| Executable missing or `OSError` at spawn | `spawn_failed` | 3 | HALT; evidence records diagnostic |
| Registry deadline expires | `timed_out` | 4 | HALT; child is killed and collected |
| Process exits non-zero | `failed` | child exit if 1–125, otherwise 1 | HALT; evidence records original exit |
| Internal serialization / persistence failure | `failed` | 1 | HALT; do not claim evidence |

The executor uses `subprocess.Popen(argv, cwd=resolution.cwd, stdout=PIPE, stderr=PIPE)` and `communicate(timeout=resolution.timeout_seconds)`. It kills and collects on timeout. It calculates byte counts, limits any diagnostic/log material to a fixed bound, and does not use output as a structured input. It must not import `loop.runtime.dispatch` or `loop.board_launch.loop_run`; the latter is a useful implementation precedent, not a dependency or generic runner.

### Phase data flow

```text
[decompose sNN capability_checks]
             |
             | strict Pydantic parse; target required
             v
[context_loop.check_after current armed step]
             |
             | project root + CapabilityCheckSpec
             v
[resolve_capability]
  manifest -> containment -> named target -> registry -> argv/cwd/timeout
             |
             | only when resolution.ok
             v
[stack_profiles executor]
  Popen(list argv, resolved cwd, registry timeout, no shell)
             |
             +--> [execution evidence JSON] --> [finish/validate step fingerprint gate]
             |
             +--> succeeded: continuation | failed: HALT + diagnostic
```

### Evidence and phase policy

1. `capability_checks` is empty for a hub-only shard. Existing explicit hub `tests:` still validates as hub evidence.
2. If a shard declares one or more capability checks, finish requires matching successful evidence for **all** declarations. A raw `tests:` value cannot satisfy any of them.
3. The phase runner does not infer target from a manifest. It does not execute capabilities outside the current step, even if an old sidecar exists.
4. Evidence matching uses a canonical model dump/hash that includes project root identity, role, epic, step, decompose ref, capability, target and selector. Changed declaration invalidates prior evidence.
5. QA plan/decompose must list every managed target/capability it claims to cover. `test.full` for one target is not an implicit monorepo full suite.
6. An implementation agent may call `python -m loop.stack_profiles execute` for local diagnosis, but only `check-after` persistence is authoritative for phase gate evidence.

### Workflow wording migration

The canonical source is `harness/cursor/rules/**` because `.cursor/rules` is a symlink shell. Rules must use an explicit two-branch formulation:

| Context | Required wording / behavior |
|---|---|
| Hub self-test | Continue using `bin/pytest`/approved hub runner and timeout contract. Do not resolve stack profile. |
| Managed project IMPLEMENT/TASK/BUGFIX | Put explicit `capability_checks` in the current decompose/task artifact; run/check evidence through profile executor; targeted test uses selector. |
| Managed project QA | Declare a complete named target matrix (including non-Python targets) and `test.full` / required quality capabilities; phase is green only after every evidence record succeeds. |
| FRONT browser scenario | Parent-only authority remains. A browser scenario remains its current explicit runner until a separately approved `test.e2e` vocabulary exists. |
| INTEG | API contract and frontend scenario rules remain; a managed backend quality check is capability-driven rather than hardcoded pytest. |

### Failure matrix

| Component / link | Failure | Detection | System response | Test ID |
|---|---|---|---|---|
| Decompose declaration | Missing target / unknown key / selector misuse | Pydantic validation | Reject shard before phase execution; no process. | TM-001 |
| Resolver | Missing/invalid manifest, unsafe root, unknown target/profile | Existing stable diagnostic | `resolution_failed`, exit 2, HALT. | TM-002 |
| JS selection | Zero/multiple lockfiles or unsafe script | Resolver diagnostic | No argv/spawn; evidence fail. | TM-003 |
| Executor spawn | Tool absent / `OSError` | Catch at subprocess boundary | `spawn_failed`, exit 3, HALT. | TM-004 |
| Executor runtime | Deadline expired | `TimeoutExpired` | Kill/collect, `timed_out`, exit 4, HALT. | TM-005 |
| Target command | Non-zero test/lint/build | Return code | `failed`, preserve code, HALT. | TM-006 |
| Evidence store | Wrong role/epic/step/fingerprint / partial write | Schema+fingerprint+atomic write | Reject stale/mismatched proof. | TM-007 |
| Finish validator | Managed declaration accompanied only by string `tests:` | Validation branch | DENY finish with evidence-missing diagnostic. | TM-008 |
| Instruction surface | Rule still teaches generic managed pytest | Scoped `rg`/literal rule test | Kind I leftover; purge step fails. | TM-009 |
| Hub tests | No manifest but hub test canon is valid | Context classification test | Continue with hub runner; executor not called. | TM-010 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|---|---:|---|
| Data flow complete | 5 | Request → resolver → executor → evidence → phase/finish gate has six explicit ownership boundaries. |
| Failure coverage | 5 | Covers declaration, resolver, spawn, timeout, target non-zero, persistence, stale evidence and Kind I drift. |
| Testability | 5 | Each layer has fake executable / temporary monorepo tests; integration proves subprocess and phase enforcement. |

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
|---|---|---|
| `harness/hooks/tests_format.py::is_allowed_test_command` as generic workflow-process gate | Explicit hub-test validator plus typed `capability_checks`/evidence validator | delete in-epic |
| `harness/hooks/tests_format.py::extract_test_commands_from_yaml_tests` as universal execution evidence | Hub-only extraction; managed evidence reader/fingerprint matcher | delete in-epic |
| `harness/hooks/test_run_canon.py::ALLOWED_TEST_PREFIXES` as managed-target authority | Narrow hub-only prefix canon; registry-owned executor for managed target | delete in-epic |
| Absent profile executor / evidence module | `loop.stack_profiles.executor` + `evidence` | add in-epic |
| `loop/context_loop.py` no-op relative to capability declaration | current-step declared-check execution gate | delete in-epic (old absence) |

### B. Entrypoints / deploy

| Устаревает (entrypoint / CLI) | Замена | Policy |
|---|---|---|
| `python -m loop.stack_profiles resolve` as the only operational profile CLI | Add `execute` JSON CLI; retain `resolve` as read-only API, not compatibility route | keep (different operation) |
| `check-after` green path without managed check execution | `check-after` executes/persists declared checks before continuation | delete in-epic |
| `epic_resolve format_spec_lines` assertion that loop runs all YAML shell strings | Typed managed evidence instruction plus explicit hub-test branch | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает (pattern) | Замена (fail-closed) | Policy |
|---|---|---|
| Missing/invalid profile declaration silently falls back to command prose | `capability_declaration_invalid` / resolver diagnostic and no subprocess | delete in-epic |
| Managed target omitted and manifest default/current directory is used | Required declaration target; `capability_target_required` | delete in-epic |
| Command result unavailable but agent writes `PASS` in implement YAML | Evidence fingerprint + finish gate | delete in-epic |
| Failed target command reinterpreted as hub self-test or retry | Return failure/HALT with no alternate command | delete in-epic |

### I. Instruction surfaces

| Устаревает (prompt / rule / skill text) | Замена | Policy |
|---|---|---|
| `harness/cursor/rules/shared/test-timeout.mdc` says all workflow tests are a hardcoded Python/full pytest suite | Separate hub runner canon from managed capability timeout/execution contract | delete in-epic |
| BACK main/core/lean workflows prescribe `.venv/bin/pytest` or `bin/pytest` for any managed backend | Explicit capability declaration/evidence wording; hub exception | delete in-epic |
| INTEG core/lean/QA workflows prescribe pytest as managed API quality default | Capability-driven managed checks plus unchanged scenario requirement | delete in-epic |
| `harness/claude/skills/role-command/SKILL.md` universal pytest wording | Runtime-parity wording that branches by hub vs managed project | delete in-epic |
| `harness/hooks/epic_yaml.py::format_spec_lines` “loop runs these strings as shell” prose | Typed evidence / no arbitrary shell instruction | delete in-epic |

## QA consumes (test plan)

### Scope under test

- Epic surfaces: strict declaration schema, resolver-to-executor boundary, CLI JSON/exit mapping, sidecar persistence/fingerprint, `check-after` enforcement, finish validation and canonical rule migration.
- Out of scope: actual package installation, custom registry profiles, browser/E2E capability vocabulary, process output archival/streaming, automatic remediation and any target command outside the six existing capabilities.

### Test matrix

| ID | P | Scenario | Command / fixture | Expected | Maps |
|---|---|---|---|---|---|
| TM-001 | P0 | Declaration rejects missing target, raw command/cwd/env and invalid selector. | New schema unit tests. | Strict error, subprocess mock untouched. | FR-001,6; AC 2; AC−1,3 |
| TM-002 | P0 | Python/Rust/JS `test.full` exact resolved argv/cwd is executed once. | Temporary three-target monorepo + fake executables/managers. | Three `succeeded` records with matching fingerprint. | FR-002,4; SC-001; AC 1,7 |
| TM-003 | P0 | Ambiguous JS and root/target resolver errors do not spawn. | Temporary manifest/lockfile negative matrix. | `resolution_failed`, argv empty/no subprocess. | FR-003; SC-002; AC−2 |
| TM-004 | P0 | Spawn error and non-zero target command have JSON/typed failures. | Fake executable absent/returns 17. | Stable result, expected non-zero CLI, phase HALT. | FR-004,5,7; SC-003 |
| TM-005 | P0 | Timeout kills and collects child at registry deadline. | Sleeping fake executable with lowered test registry fixture. | `timed_out`, exit 4, bounded result, no green continuation. | FR-002,4,7; AC−2 |
| TM-006 | P0 | Current armed step checks execute during check-after and persist evidence. | Context-loop fixture with one capability check. | Call order resolve → execute → atomic evidence → success continuation. | FR-007; SC-003; AC 2,3 |
| TM-007 | P0 | Stale/wrong target/step fingerprint cannot satisfy finish. | Reuse sidecar from another check/step. | `capability_evidence_missing_or_mismatch`; finish denied. | FR-008; SC-004; AC 4 |
| TM-008 | P1 | Existing hub `tests:` fixtures remain accepted and do not call executor. | Existing finish/format tests + executor mock. | Existing hub command canon green; zero resolver calls. | FR-008,12; SC-005; AC 5 |
| TM-009 | P1 | Managed declaration cannot be proven by raw shell string. | Implement YAML with `capability_checks` plus only `tests:`. | Validator rejects; no fallback. | FR-008,11; SC-004; AC−2,5 |
| TM-010 | P1 | Rules/format prompt expose new managed path and retain hub-only language. | Literal/instruction inventory test and scoped `rg`. | No forbidden generic managed runner text. | FR-009–11; SC-006; AC 6 |
| TM-011 | P1 | Direct `execute` CLI JSON equals API result for pass/failure. | CLI subprocess test with fake target. | Same schema fields and exit mapping. | FR-005; US-003 |

### Regression notes

- Run new target tests with hub `bin/pytest`, because these are tests of dev-hub itself, not profile execution.
- Tests that launch fakes must control `PATH`, use temporary roots and assert `shell` is absent/false; they must not invoke the host cargo/npm project scripts.
- Timeout test must use a fixture-owned minimal deadline only through a test registry fixture; production registry remains 300 seconds.
- Existing hub test-format fixtures are regression evidence. Rewrite expected names/prose where semantics change, but do not delete their coverage.

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| CLARIFY / Product probe | L3 | done | Phase 0 taxonomy-clear rationale + Product probe table. |
| Eng review spine | L2+ | done | Data flow, failure matrix and scores above. |
| §0.11 counterparts (draft) | external/runtime boundary | done | Resolver → executor → context loop → evidence → finish validator mapped in ownership table. |
| CREATIVE | if flagged | n/a | No UI / visual asset. |
| qa_consumes draft | L2+ | done | TM-001…TM-011, seven P0/P1 behavioral rows. |
| Plan review batch | L2+ | done | Log below; no unresolved Required item. |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner / next) | Taste / CRITICAL surfaced |
|---|---|---|---|
| Product | One wedge executes only existing verification vocabulary; explicit target required for auditable workflow execution. | Browser/E2E vocabulary, package installation and profile version floors: later product decision. | Do not claim a shell-string migration is execution wiring. |
| Eng | Separate executor from agent runtime dispatch; use sidecar evidence and current-step check-after gate; preserve hub tests as separate domain. | Exact bounded log retention/diagnostic redaction policy may be finalized during s01 but must not expose output in YAML. | Any optional execution/default target/raw command path is a CRITICAL reject. |

## До DECOMPOSE (черновик нарезки)

1. **s01 — strict execution/declaration schema red:** typed Pydantic models, diagnostics, canonical fingerprint and negative declaration tests.
2. **s02 — argv-only executor + result:** resolver-to-subprocess service, spawn/timeout/non-zero handling and three-profile fake integration tests.
3. **s03 — JSON execute CLI + evidence persistence:** CLI parity, typed result exit mapping and atomic sidecar read/write/fingerprint tests.
4. **s04 — check-after wire/enforce:** current armed step discovery, declared checks execution, continuation HALT and evidence test seam.
5. **s05 — finish/schema evidence migration:** decompose/implement/finish models validate managed evidence versus declaration while retaining explicit hub-test branch.
6. **s06 — workflow instruction + legacy-fallback purge:** canonical harness rules/role text and format prose migration; A/B/C/I inventories, no generic managed runner leftovers, full regression.

DECOMPOSE must make the ladder visible as **add → wire → enforce → purge**, include all Kind I rows and avoid a separate cosmetic “tests only” step. Each sNN has behavior evidence; last sNN runs the complete sunset inventory.

## Appetite

| Field | Value |
|---|---|
| `timebox_days` | 4 |
| `cut_list` | `['test.e2e capability', 'profile version floors', 'custom/remote profiles', 'package installation', 'target command streaming UI', 'automatic remediation']` |

## Independent Test

Create a temporary managed monorepo with explicit `py`, `rs` and `web` targets. Each target exposes a fake executable or manager that writes its received argv/cwd and exits as configured. Declare three `test.full` checks in an armed step and call `check-after`: assert exact resolver-owned argv/cwd, three matching evidence records and a green continuation. Then rerun with one missing target declaration, ambiguous JS locks, absent executable, timeout, non-zero exit and stale sidecar: every case must HALT without fallback or extra subprocess. Separately execute an existing hub finish fixture and assert it still uses hub test validation with zero profile-executor calls.

## Следующий режим

→ `BACK DECOMPOSE T-HUB-076-stack-profile-capability-execution` after T-HUB-075 BACK QA is PASS.
