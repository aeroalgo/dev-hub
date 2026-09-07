# [T-HUB-075 | stack-profiles-rust-python-js] PLAN

**Дата:** 2026-09-06  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** [clarify-20260906-stack-profiles-rust-python-js.md](../../../clarify/clarify-20260906-stack-profiles-rust-python-js.md)  
**Prompt:** [md/prompt.md](prompt.md) — outcome SoT, не HOW  
**Deps:** hard T-HUB-067 (единая форма doctor); soft T-HUB-062 (canonical skill topology). Runtime adapters T-HUB-042–044 не являются зависимостью.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** запрос пользователя, Phase 0 clarify; `loop/runtime_registry.yaml` и `loop.runtime.registry` как typed registry precedent; `loop/workflow/registry.py`; `bin/hub-link`.

→ После DECOMPOSE единственный трекер — [`md/decompose-index.md`](decompose-index.md) / [`yaml/decompose-index.yaml`](../yaml/decompose-index.yaml); sNN-checkbox здесь не дублируются.

## Контекст

dev-hub выбирает runtime агента и workflow pack, но не выражает стек **управляемого продукта**. Поэтому rules/formula легко получают Python/JS literals. Эпик добавляет узкий quality-port, а не превращает hub в benchmark harness или arbitrary shell runner.

Границы:

1. **Hub self-test** — `bin/pytest`, `loop/tests`, `harness/hooks/tests`: Python tooling самого hub; не target capability и не объект миграции.
2. **Managed project** — подключивший hub репозиторий с `dev-hub.project.yaml`; только ему resolver выдаёт argv Rust/Python/JS.
3. **Runtime adapter** — Claude/Codex/DSH; выбор запуска агента, не stack profile.
4. **Workflow pack** — роли/phases/layout; он потребляет API capability, но не хранит команды стека.

**CREATIVE need:** нет.

## Technology axiom (replace-not-wrap)

| Выбор | Machine SoT | FORBIDDEN после эпика |
|---|---|---|
| Project config | `dev-hub.project.yaml` + Pydantic `ProjectManifest` | `project.yaml`/`.dev-hub/project.yaml` parser fallback |
| Profile | typed `python|rust|javascript`, named target | inference по marker-файлам при resolve |
| Capability | fixed enum + `CapabilityRequest` | shell string, `bash -c`, `eval`, supplied argv/env |
| Result | `CapabilityResolution` JSON, `argv: list[str]` | prose command как machine API |
| JS manager | one lockfile или explicit override | silent npm/pnpm default |
| Errors | `ok=false`, diagnostic code, non-zero exit | fallback к Python, nearest manifest search, no-op |

Новый manifest — единственный config path для profile selection и workflow-pack project override. Старые locations удаляются из machine discovery в этом эпике, а не читаются вторым путём.

## Продуктовая спека (WHAT)

### Product probe

| # | Probe | Decision / impact |
|---|---|---|
| 1 | Reframe | Не три aliases, а port «workflow intention → target argv». |
| 2 | Narrowest wedge | Built-in Python/Rust/JS + six verify-first capabilities. |
| 3 | Pre-mortem | Arbitrary shell и pnpm lock-in → argv-only and lockfile policy. |
| 4 | Adoption | Hub link → explicit manifest → doctor/resolve. |
| 5 | Leverage | Existing Pydantic/YAML registries; separate module, not runtime registry. |
| 6 | Appetite | 4 days; cut convenience init/version ranges before safety. |

### User Stories

| # | Story | P | Independent Test |
|---|---|---|---|
| US-001 | Rust owner resolves a quality operation without Python fallback. | P0 | `test.full` returns exact cargo argv. |
| US-002 | Python owner receives argv/cwd, not shell text. | P0 | targeted selector remains one argv atom. |
| US-003 | JS owner never gets an assumed manager on conflicting lockfiles. | P0 | conflict emits only diagnostic. |
| US-004 | Monorepo owner selects named target/default safely. | P0 | two targets/no default fails. |
| US-005 | Workflow/skill author requests a stable capability, not a command. | P1 | API and CLI have identical JSON result. |
| US-006 | Operator sees blockers before running project code. | P1 | doctor uses probes only. |

### Acceptance Scenarios

#### US-001

- **Given:** `api` has profile `rust`, root `services/api`, `Cargo.toml`.
- **When:** `resolve_capability(..., target="api", capability="test.full")`.
- **Then:** `ok=true`, `cwd=<workspace>/services/api`, `argv=["cargo","test","--all-targets"]`, `profile="rust"`; Python files are irrelevant.

#### US-003

- **Given:** JS target has `pnpm-lock.yaml` and `package-lock.json`, no override.
- **When:** resolve or doctor runs.
- **Then:** `js_package_manager_ambiguous`, non-zero, no argv.

#### US-004

- **Given:** manifest has `backend` and `frontend`, no default.
- **When:** caller omits target.
- **Then:** `target_selection_required`, not current directory/alphabetical/recursive discovery.

### Functional Requirements

- **FR-001:** `dev-hub-project/v1` Pydantic schema permits only `schema`, optional `workflow_pack`, optional `default_target`, `targets`; unknown keys fail.
- **FR-002:** Target has stable name, workspace-relative `root`, profile `python|rust|javascript`, only profile-specific typed overrides. Canonical root stays in workspace; duplicate name/root fails.
- **FR-003:** Resolver reads only root `dev-hub.project.yaml`; it never walks parent/child directories or infers profile from `Cargo.toml`, `pyproject.toml`, `package.json`.
- **FR-004:** `.dev-hub` remains the one-line `hub-link` pointer, never YAML/config directory.
- **FR-005:** Replace `loop.workflow.registry._read_project_yaml_pack()` reads from `project.yaml` and `.dev-hub/project.yaml` with typed optional `workflow_pack` from new manifest. Default/env workflow-pack still work when no new manifest exists.
- **FR-006:** Ship immutable local `stack-profile-registry/v1` with exactly `python`, `rust`, `javascript`; manifest cannot provide command, argv, shell, env, cwd, import or registry path.
- **FR-007:** V1 vocabulary is exactly `format.check`, `lint`, `typecheck`, `test.targeted`, `test.full`, `build`. Unknown/run/migrate/generate/deploy fails `capability_unknown`.
- **FR-008:** `test.targeted` requires nonempty selector; all other keys reject selector. Selector is one argv atom, never a concatenated shell fragment.
- **FR-009:** Commands are deterministic: Python = `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy .`, `python -m pytest [selector]`, `python -m build`; Rust = `cargo fmt -- --check`, `cargo clippy --all-targets -- -D warnings`, `cargo check --all-targets`, `cargo test [-- selector]`, `cargo build --all-targets`; JS = selected manager `run` safe labels `format:check`, `lint`, `typecheck`, `test`, `build`, target selector appended as `--`, selector.
- **FR-010:** JS chooses exactly one supported lockfile (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`/`bun.lockb`) or explicit supported `package_manager`. None/many without override fail; safe script-label override is JS-only.
- **FR-011:** Public resolver returns schema ID, `ok`, target/profile/capability, absolute `cwd`, `argv`, `timeout_seconds`, requirements, ordered diagnostics. It never executes target commands.
- **FR-012:** `python -m loop.stack_profiles resolve|doctor` is JSON-first. `resolve` exits 0 only with complete result; doctor may inspect files and call executable `--version` under fixed short timeout, never test/build scripts.
- **FR-013:** YAML/schema/root/profile/capability/selector/lockfile/tool failures have stable diagnostics, empty argv and nonzero status. No default Python/JS/target fallback.
- **FR-014:** Consumers use `resolve_capability()` only. Wiring an actual phase to execute commands is a future epic that declares its own capability.
- **FR-015:** `bin/pytest`, `harness/hooks/test_run_canon.py`, `loop/incidents/tier1_verify.py`, `loop/tests/**` remain hub self-test; no migration through target profiles.
- **FR-016:** Delete legacy project config reader, tests and instructions in the same epic; do not leave `try new except old`.
- **FR-017:** Add migration documentation/template for old workflow config locations.

### Success Criteria

| ID | Result | Verification |
|---|---|---|
| SC-001 | Six capabilities resolve for all three bundled profiles. | parameterized pytest |
| SC-002 | Unsafe/missing input emits code and no argv. | negative matrix |
| SC-003 | JS ambiguity cannot choose a manager. | API + JSON CLI |
| SC-004 | Multi-target repo cannot choose silently. | pytest |
| SC-005 | Legacy workflow config is never read after cutover. | pytest + rg |
| SC-006 | Doctor never invokes application scripts. | fake executable log |

### Assumptions / Clarifications

- Canonical Phase 0 decisions: profiles+capabilities only; lockfile-first JS; separate manifest; named targets; verify-first vocabulary.
- Bundled defaults are opinionated. Missing ruff/mypy/scripts produces diagnostic; resolver invents no alternate tool.
- `timeout_seconds=300` is metadata for future execution owner. Doctor probe uses separate short timeout.
- Out: remote/custom profiles, dynamic skill installation, tool install, nested configs, version range enforcement, run/migrate/deploy.
- Tool version floor is IMPORTANT but deferred: doctor reports observed availability; future profile-version epic owns mandated floors.

## AC

1. One typed manifest selects Python/Rust/JS targets without conflating `.dev-hub`, runtime or workflow pack.
2. Every v1 capability maps to structured argv/cwd for each profile.
3. JS ambiguity stops before argv emission.
4. Target selection/root containment are explicit and safe.
5. API and CLI expose same machine result, never prose parsing.
6. Doctor detects blockers without target-script execution.
7. Old config locations are removed from machine discovery and migration is documented.
8. Hub self-test command canon is unchanged.

### AC−

1. No `shell=True`, `bash -c`, `eval`, interpolated command, supplied argv/env.
2. No `project.yaml`/`.dev-hub/project.yaml` fallback.
3. No implicit target/profile/package-manager choice.
4. No capabilities outside verify-first six.
5. No remote plugin/profile search path.
6. No change to hub-only pytest canon disguised as stack support.

## Техника / архитектура (HOW)

| Surface | Ownership | Consumers |
|---|---|---|
| `loop/stack_profiles/schemas.py` | strict models, vocabulary, diagnostic/result shapes | resolver/CLI/tests |
| `loop/stack_profiles/registry.py` | validate cached bundled registry relative to hub root | resolver/doctor |
| `loop/stack_profiles/resolver.py` | manifest, containment, target, JS manager, argv; pure | workflow/skills/CLI |
| `loop/stack_profiles/doctor.py` | preflight and no-script probes | CLI/future doctor |
| `loop/stack_profiles/__main__.py` | parser + JSON/exit mapping | operator |
| `loop/stack_profiles/registry.yaml` | profiles/templates/required executables | registry only |
| `loop/workflow/registry.py` | typed `workflow_pack`, no legacy parser | pack resolution |
| `loop/tests/test_stack_profiles_*.py` | contract, negative, CLI, doctor, migration | CI |
| `harness/templates/dev-hub.project.yaml` | safe template, not executable config | users |
| `README.md`, `harness/README.md` | usage and migration/boundary docs | users |

### Canonical manifest

```yaml
schema: dev-hub-project/v1
workflow_pack: dev-hub-software
default_target: backend
targets:
  backend:
    root: services/backend
    profile: python
  worker:
    root: services/worker
    profile: rust
  web:
    root: apps/web
    profile: javascript
    package_manager: pnpm
    scripts:
      test.targeted: test
      test.full: test
```

`scripts` only exists for javascript. Values are strict non-whitespace script identifiers; profile templates own manager invocation. Python/Rust cannot add `scripts`, `argv`, `command`, `cwd`, `env`, `shell`, `registry`.

### Public API / CLI

```python
def load_project_manifest(project_root: Path) -> ProjectManifest: ...
def resolve_capability(project_root: Path, capability: CapabilityName, *, target: str | None = None, selector: str | None = None) -> CapabilityResolution: ...
def doctor_project_profiles(project_root: Path, *, target: str | None = None) -> DoctorReport: ...
```

```text
python -m loop.stack_profiles resolve --project-root /repo --target worker --capability test.full
python -m loop.stack_profiles resolve --project-root /repo --target backend --capability test.targeted --selector tests/test_health.py::test_ready
python -m loop.stack_profiles doctor --project-root /repo --target web
```

Exit: `0` complete; `2` config/profile diagnostics; `3` missing/probe-failed tool; `1` unexpected internal error. Stdout is JSON.

### Data flow

```text
[project root] -> [dev-hub.project.yaml] -> [ProjectManifest]
                                                 |
                          root containment + target/default selection
                                                 v
[stack-profile-registry/v1] -> [profile template] <- [lockfile or JS override]
                                                 |
                          [CapabilityRequest + selector validation]
                                                 v
          [CapabilityResolution: argv[], cwd, requirements, diagnostics]
                         |                           |
                         v                           v
                  [CLI JSON]              [workflow/skill Python API]
```

### Failure matrix

| Link | Failure | Response | Test |
|---|---|---|---|
| manifest | missing/malformed/unknown key | `project_manifest_missing|invalid`, argv empty | TM-001/002 |
| root | external/nonexistent/duplicate | `target_root_unsafe|missing|duplicate` | TM-003 |
| selection | multiple/no default | `target_selection_required` | TM-004 |
| profile/capability | unknown | `profile_unknown|capability_unknown` | TM-005/006 |
| selector | absent for targetted/present for other | `selector_required|forbidden` | TM-006 |
| JS | zero/many lockfiles | `js_package_manager_missing|ambiguous` | TM-007 |
| JS override | unsupported manager/unsafe script | `js_package_manager_invalid|js_script_invalid` | TM-008 |
| tool | missing or probe fails | doctor code, exit 3 | TM-009 |
| legacy | old config exists | detect/reject; never parse | TM-010 |
| doctor | a project script gets executed | fake log must stay empty | TM-011 |

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| `_read_project_yaml_pack()` and untyped old YAML reads | `load_project_manifest().workflow_pack` | delete in-epic |
| tests asserting old config precedence | typed manifest/migration negative tests | rewrite in-epic |
| future consumer tool literals | resolver result | delete when consumer migrates |
| `formula_render.py` default pytest / incident checks | hub self-test, not target command | keep, documented n/a |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| docs for project config at `project.yaml`/`.dev-hub/project.yaml` | root `dev-hub.project.yaml` | delete in-epic |
| treating `.dev-hub` as config directory | pointer-only `hub-link` semantics | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| inferred profile | `targets.*.profile` | delete in-epic |
| assumed JS manager | one lockfile/explicit override | delete in-epic |
| first/current target choice | explicit target/default | delete in-epic |
| new parser failure → old parser | typed diagnostic | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| config docs teaching old locations | template + migration | delete in-epic |
| `.dev-hub` shown as YAML | one-line pointer explanation | delete in-epic |
| guidance to embed pytest/cargo/npm in generic consumer | fixed capability request | rewrite in-epic where found |

## NFR

| ID | Requirement |
|---|---|
| NFR-1 | Resolver has no network/install/shell/target-script execution. |
| NFR-2 | All YAML boundaries use Pydantic `extra="forbid"`. |
| NFR-3 | Root containment uses resolved `Path`, never prefix string checks. |
| NFR-4 | Expected CLI failures preserve JSON output. |
| NFR-5 | Registry is local/immutable; no remote lookup. |
| NFR-6 | Doctor probes have fixed low timeout and no secret output. |
| NFR-7 | argv boundaries never become `shlex.join` machine input. |

## QA consumes (test plan)

### Scope under test

Manifest/registry schema, containment, target selection, three profiles, JS policy, JSON CLI/exit, doctor no-script property and legacy discovery purge. Out: actual product test/build execution, profiles from users, package install and hub self-tests.

| ID | P | Scenario | Fixture / expected | Maps |
|---|---|---|---|---|
| TM-001 | P0 | missing manifest | code, argv `[]`, exit 2 | FR-003,13 |
| TM-002 | P0 | unknown key/malformed YAML | strict invalid code | FR-001,13 |
| TM-003 | P0 | escape/absolute/missing roots | no cwd outside workspace | FR-002 |
| TM-004 | P0 | 2 targets/no default | selection required | FR-002,3 |
| TM-005 | P0 | Python all 6 | exact argv/cwd | FR-006–09 |
| TM-006 | P0 | Rust all 6 | exact cargo argv, no Python | FR-006–09 |
| TM-007 | P0 | JS one lockfile each | exact manager/script argv | FR-009,10 |
| TM-008 | P0 | JS zero/two locks/override | fail or explicit success | FR-010 |
| TM-009 | P0 | selector cases/argv atom | no shell command field | FR-007,8,11 |
| TM-010 | P1 | tool missing/probe timeout | exit 3, no script log | FR-012,13 |
| TM-011 | P0 | legacy config only | detected, never used | FR-005,16,17 |
| TM-012 | P1 | workflow_pack in new manifest | documented env/default precedence | FR-005 |
| TM-013 | P1 | docs inventory | no live old parser/instruction | FR-017 |
| TM-014 | P1 | self-test boundary | existing pytest canon unchanged | FR-015 |

Regression: targeted `bin/pytest loop/tests/test_stack_profiles_*.py loop/tests/test_workflow_registry.py -q --tb=line`, then `bin/pytest loop/tests/ -q --tb=line`. Tests use fixtures/fake executable probes; they do not run Rust/JS project scripts.

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| CLARIFY / Product probe | L3 | done | clarify artifact + probe |
| Eng review spine | L2+ | done | ownership/API/flow/failure matrix |
| counterparts | external | done | manifest→resolver→CLI→doctor→workflow reader |
| CREATIVE | if flagged | n/a | no UI |
| qa_consumes | L2+ | done | 14 rows, ≥3 P0 |
| Plan review batch | L2+ | done | below |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Critical |
|---|---|---|---|
| Product | One internal profile contract, no marketplace, verify-first. | tool version floors/dynamic extensions → later epic | arbitrary shell eliminated |
| Eng | Pydantic/YAML local registry; separate stack module; explicit self-test boundary. | phase-level capability declarations → later consumer epic | legacy config must purge |

## До DECOMPOSE (черновик нарезки)

1. Red schema/manifest/containment/vocabulary tests and strict models.
2. Bundled registry plus pure Python/Rust/JS resolver and selector/JS logic.
3. JSON CLI plus no-script doctor and fake executable tests.
4. Wire workflow registry to new typed config; migrate template/docs/tests.
5. Consumer-facing API integration test, without lifecycle execution.
6. Final `legacy-fallback-purge`: A+B+C+I inventory, rg controls, full regression.

DECOMPOSE must follow add → wire → enforce → purge, and mirror every sunset row.

## Appetite

| Field | Value |
|---|---|
| `timebox_days` | 4 |
| `cut_list` | `['manifest-writing init', 'minimum version enforcement', 'custom profiles', 'pack phase declaration syntax']` |

## Independent Test

Create a temporary monorepo with Python, Rust and JS named targets. Resolve `test.full` for each and assert exact JSON. Remove default, add a second JS lockfile and make a target root escape: all must fail with distinct codes and no argv. Presence of YAML/classes alone is not evidence.

## Следующий режим

→ `BACK ANALYZE T-HUB-075-stack-profiles-rust-python-js` (decompose tree 6 sNN; ANALYZE deferred FORBIDDEN).
