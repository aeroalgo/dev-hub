# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-075-stack-profiles-rust-python-js  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-07  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 6 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 6; TDD red schema/containment/vocabulary в s01; bundled registry+pure resolver в s02; JSON CLI+no-script doctor в s03; wire+enforce workflow_pack cutover в s04; consumer API integration без lifecycle в s05; apply≠purge → s06)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-075-stack-profiles-rust-python-js/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (red tests + strict models) → s02 add (bundled registry + pure resolver argv/cwd) → s03 add+enforce (JSON CLI + doctor probes, DENY script exec) → s04 wire+enforce (typed `workflow_pack` sole path; delete `_read_project_yaml_pack`) → s05 wire (consumer `resolve_capability` integration, no lifecycle) → s06 leftover inventory scan (apply≠purge).  
> **Justification 6 sNN:** plan §До DECOMPOSE enumerates 6 outcomes; s01 TDD/schema ≠ s02 resolver argv; s03 CLI/doctor is independent operator surface (US-006/FR-012); s04 workflow-pack cutover ≠ s05 consumer API (FR-014 no-lifecycle); s06 leftover inventory ≠ apply. TDD red is s01 not a seventh tests-only step.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-type-safety` | Pydantic extra=forbid, enum vocabulary, result shapes (s01–s03) |
| `python-error-handling` | diagnostic codes, empty argv, nonzero CLI (s02–s04, s06) |
| `python-configuration` | YAML/manifest load, env/default pack precedence (s01, s04) |
| `python-observability` | doctor probe timeout, no secret output (s03) |

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap-*.queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | `dev-hub-project/v1` Pydantic schema permits only `schema`, optional `workflow_pack`, optional `default_target`, `targets`; unknown keys fail. | s01, s06 | extra=forbid |
| FR-002 | Target has stable name, workspace-relative `root`, profile `python\|rust\|javascript`, only profile-specific typed overrides. Canonical root stays in workspace; duplicate name/root fails. | s01, s02, s06 | containment |
| FR-003 | Resolver reads only root `dev-hub.project.yaml`; it never walks parent/child directories or infers profile from `Cargo.toml`, `pyproject.toml`, `package.json`. | s01, s02, s06 | no recursive search |
| FR-004 | `.dev-hub` remains the one-line `hub-link` pointer, never YAML/config directory. | s04, s06 | Kind B/I |
| FR-005 | Replace `loop.workflow.registry._read_project_yaml_pack()` reads from `project.yaml` and `.dev-hub/project.yaml` with typed optional `workflow_pack` from new manifest. Default/env workflow-pack still work when no new manifest exists. | s04, s06 | cutover |
| FR-006 | Ship immutable local `stack-profile-registry/v1` with exactly `python`, `rust`, `javascript`; manifest cannot provide command, argv, shell, env, cwd, import or registry path. | s01, s02, s06 | bundled registry |
| FR-007 | V1 vocabulary is exactly `format.check`, `lint`, `typecheck`, `test.targeted`, `test.full`, `build`. Unknown/run/migrate/generate/deploy fails `capability_unknown`. | s01, s02, s05 | enum |
| FR-008 | `test.targeted` requires nonempty selector; all other keys reject selector. Selector is one argv atom, never a concatenated shell fragment. | s01, s02, s05 | argv atom |
| FR-009 | Commands are deterministic: Python = `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy .`, `python -m pytest [selector]`, `python -m build`; Rust = `cargo fmt -- --check`, `cargo clippy --all-targets -- -D warnings`, `cargo check --all-targets`, `cargo test [-- selector]`, `cargo build --all-targets`; JS = selected manager `run` safe labels `format:check`, `lint`, `typecheck`, `test`, `build`, target selector appended as `--`, selector. | s02, s05 | exact argv |
| FR-010 | JS chooses exactly one supported lockfile (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`/`bun.lockb`) or explicit supported `package_manager`. None/many without override fail; safe script-label override is JS-only. | s02, s05, s06 | no silent npm |
| FR-011 | Public resolver returns schema ID, `ok`, target/profile/capability, absolute `cwd`, `argv`, `timeout_seconds`, requirements, ordered diagnostics. It never executes target commands. | s02, s03, s05 | CapabilityResolution |
| FR-012 | `python -m loop.stack_profiles resolve\|doctor` is JSON-first. `resolve` exits 0 only with complete result; doctor may inspect files and call executable `--version` under fixed short timeout, never test/build scripts. | s03, s06 | doctor no-script |
| FR-013 | YAML/schema/root/profile/capability/selector/lockfile/tool failures have stable diagnostics, empty argv and nonzero status. No default Python/JS/target fallback. | s01, s02, s03, s06 | fail-closed |
| FR-014 | Consumers use `resolve_capability()` only. Wiring an actual phase to execute commands is a future epic that declares its own capability. | s05 | no lifecycle; Appetite cut pack phase declaration |
| FR-015 | `bin/pytest`, `harness/hooks/test_run_canon.py`, `loop/incidents/tier1_verify.py`, `loop/tests/**` remain hub self-test; no migration through target profiles. | s05, s06 | documented n/a keep |
| FR-016 | Delete legacy project config reader, tests and instructions in the same epic; do not leave `try new except old`. | s04, s06 | purge dual path |
| FR-017 | Add migration documentation/template for old workflow config locations. | s04, s06 | template + README |
| US-001 | Rust owner resolves a quality operation without Python fallback. | s02, s05 | P0 cargo argv |
| US-002 | Python owner receives argv/cwd, not shell text. | s02, s05 | P0 selector atom |
| US-003 | JS owner never gets an assumed manager on conflicting lockfiles. | s02, s03, s05 | P0 diagnostic only |
| US-004 | Monorepo owner selects named target/default safely. | s01, s02, s05 | P0 selection required |
| US-005 | Workflow/skill author requests a stable capability, not a command. | s03, s05 | P1 API=CLI JSON |
| US-006 | Operator sees blockers before running project code. | s03 | P1 doctor probes |
| SC-001 | Six capabilities resolve for all three bundled profiles. | s02, s05 | parameterized pytest |
| SC-002 | Unsafe/missing input emits code and no argv. | s01, s02, s03 | negative matrix |
| SC-003 | JS ambiguity cannot choose a manager. | s02, s03, s05 | API + JSON CLI |
| SC-004 | Multi-target repo cannot choose silently. | s01, s02, s05 | pytest |
| SC-005 | Legacy workflow config is never read after cutover. | s04, s06 | pytest + rg |
| SC-006 | Doctor never invokes application scripts. | s03, s06 | fake executable log |
| AC+1 | One typed manifest selects Python/Rust/JS targets without conflating `.dev-hub`, runtime or workflow pack. | s01, s04 | |
| AC+2 | Every v1 capability maps to structured argv/cwd for each profile. | s02, s05 | |
| AC+3 | JS ambiguity stops before argv emission. | s02, s03, s05 | |
| AC+4 | Target selection/root containment are explicit and safe. | s01, s02, s05 | |
| AC+5 | API and CLI expose same machine result, never prose parsing. | s03, s05 | |
| AC+6 | Doctor detects blockers without target-script execution. | s03, s06 | |
| AC+7 | Old config locations are removed from machine discovery and migration is documented. | s04, s06 | |
| AC+8 | Hub self-test command canon is unchanged. | s05, s06 | |
| AC−1 | No `shell=True`, `bash -c`, `eval`, interpolated command, supplied argv/env. | s02, s03, s05, s06 | |
| AC−2 | No `project.yaml`/`.dev-hub/project.yaml` fallback. | s04, s06 | |
| AC−3 | No implicit target/profile/package-manager choice. | s02, s05, s06 | |
| AC−4 | No capabilities outside verify-first six. | s01, s02, s05 | |
| AC−5 | No remote plugin/profile search path. | s02, s06 | |
| AC−6 | No change to hub-only pytest canon disguised as stack support. | s05, s06 | |
| NFR-1 | Resolver has no network/install/shell/target-script execution. | s02, s03, s05 | |
| NFR-2 | All YAML boundaries use Pydantic `extra="forbid"`. | s01, s02 | |
| NFR-3 | Root containment uses resolved `Path`, never prefix string checks. | s01, s02 | |
| NFR-4 | Expected CLI failures preserve JSON output. | s03 | |
| NFR-5 | Registry is local/immutable; no remote lookup. | s02, s06 | |
| NFR-6 | Doctor probes have fixed low timeout and no secret output. | s03 | |
| NFR-7 | argv boundaries never become `shlex.join` machine input. | s02, s03, s05 | |
| TM-001 | P0 missing manifest — code, argv `[]`, exit 2 | s01, s02, s03 | FR-003,13 |
| TM-002 | P0 unknown key/malformed YAML — strict invalid code | s01 | FR-001,13 |
| TM-003 | P0 escape/absolute/missing roots — no cwd outside workspace | s01, s02 | FR-002 |
| TM-004 | P0 2 targets/no default — selection required | s01, s02 | FR-002,3 |
| TM-005 | P0 Python all 6 — exact argv/cwd | s02, s05 | FR-006–09 |
| TM-006 | P0 Rust all 6 — exact cargo argv, no Python | s02, s05 | FR-006–09 |
| TM-007 | P0 JS one lockfile each — exact manager/script argv | s02, s05 | FR-009,10 |
| TM-008 | P0 JS zero/two locks/override — fail or explicit success | s02, s05 | FR-010 |
| TM-009 | P0 selector cases/argv atom — no shell command field | s02, s05 | FR-007,8,11 |
| TM-010 | P1 tool missing/probe timeout — exit 3, no script log | s03 | FR-012,13 |
| TM-011 | P0 legacy config only — detected, never used | s04, s06 | FR-005,16,17 |
| TM-012 | P1 workflow_pack in new manifest — documented env/default precedence | s04 | FR-005 |
| TM-013 | P1 docs inventory — no live old parser/instruction | s04, s06 | FR-017 |
| TM-014 | P1 self-test boundary — existing pytest canon unchanged | s05, s06 | FR-015 |
| Independent Test PASS | Create a temporary monorepo with Python, Rust and JS named targets. Resolve `test.full` for each and assert exact JSON. Remove default, add a second JS lockfile and make a target root escape: all must fail with distinct codes and no argv. Presence of YAML/classes alone is not evidence. | s02, s03, s05, s06 | |
| Independent Test FAIL | Presence of YAML/classes alone is not evidence. | s02, s05 | dilution = FAIL ANALYZE |
| Technology axiom Project config | `dev-hub.project.yaml` + Pydantic `ProjectManifest` | s01, s04, s06 | FORBIDDEN `project.yaml`/`.dev-hub/project.yaml` parser fallback |
| Technology axiom Profile | typed `python\|rust\|javascript`, named target | s01, s02 | FORBIDDEN inference по marker-файлам при resolve |
| Technology axiom Capability | fixed enum + `CapabilityRequest` | s01, s02, s05 | FORBIDDEN shell string, `bash -c`, `eval`, supplied argv/env |
| Technology axiom Result | `CapabilityResolution` JSON, `argv: list[str]` | s02, s03, s05 | FORBIDDEN prose command как machine API |
| Technology axiom JS manager | one lockfile или explicit override | s02, s06 | FORBIDDEN silent npm/pnpm default |
| Technology axiom Errors | `ok=false`, diagnostic code, non-zero exit | s01, s02, s03, s06 | FORBIDDEN fallback к Python, nearest manifest search, no-op |
| Appetite cut manifest-writing init | out of scope | — | cut_list; no follow_up epic |
| Appetite cut minimum version enforcement | out of scope | — | cut_list; doctor reports observed availability; future profile-version epic owns mandated floors (not in queue → no follow_up ID) |
| Appetite cut custom profiles | out of scope | — | cut_list |
| Appetite cut pack phase declaration syntax | out of scope | — | cut_list; FR-014 future consumer epic |
| Out remote/custom profiles | Out: remote/custom profiles, dynamic skill installation, tool install, nested configs, version range enforcement, run/migrate/deploy | — | Appetite + Assumptions; no queue ID |
| Out hub self-test | `formula_render.py` default pytest / incident checks remain hub self-test | s06 | plan sunset A keep, documented n/a |
| Out runtime adapters | Runtime adapters T-HUB-042–044 не являются зависимостью | — | plan Deps |
| Soft dep T-HUB-062 | canonical skill topology | — | soft; not blocking this tree |
| Hard dep T-HUB-067 | единая форма doctor | — | already in queue; doctor JSON form reused by s03 |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| s01 — Red schema/manifest/containment/vocabulary tests and strict models | plan §До DECOMPOSE 1 | s01 |
| s02 — Bundled registry plus pure Python/Rust/JS resolver and selector/JS logic | plan §До DECOMPOSE 2 | s02 |
| s03 — JSON CLI plus no-script doctor and fake executable tests | plan §До DECOMPOSE 3 | s03 |
| s04 — Wire workflow registry to new typed config; migrate template/docs/tests | plan §До DECOMPOSE 4 | s04 |
| s05 — Consumer-facing API integration test, without lifecycle execution | plan §До DECOMPOSE 5 | s05 |
| s06 — Final `legacy-fallback-purge`: A+B+C+I inventory, rg controls, full regression | plan §До DECOMPOSE 6 · Replacement | s06 |
| Completeness ladder add → wire → enforce → purge | behavior-first §3 | s01 add; s02 add; s03 add+enforce; s04 wire+enforce; s05 wire; s06 purge |
| Data flow project yaml → manifest → registry → CapabilityRequest → CLI/API | plan §Data flow | s01, s02, s03, s05 |
| Failure matrix 10 rows | plan §Failure matrix | s01–s06 (mapped per TM) |
| QA consumes test matrix TM-001…TM-014 | plan §qa-consumes | s01–s06 |
| Independent Test PASS/FAIL | plan §Independent Test | s02, s03, s05, s06 |
| Eng spine ownership/API/flow/failure matrix | plan §Техника / архитектура | s01–s05 |
| Public API `load_project_manifest` / `resolve_capability` / `doctor_project_profiles` | plan §Public API / CLI | s01, s02, s03, s05 |
| Canonical manifest example | plan §Canonical manifest | s01, s02, s04 |

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR плана до infra-slug.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Управляемый проект явно сообщает стек каждого target; workflow получает проверяемую capability без знания команд языка | s02, s05 |
| Rust/Python/JS — равноправные встроенные профили, не arbitrary shell runner | s02, s05, s06 |
| `test.full` для rust = exact cargo argv; Python files irrelevant | s02, s05 |
| Python targeted selector remains one argv atom, not shell text | s02, s05 |
| JS conflict emits only diagnostic; no assumed manager | s02, s03, s05 |
| Two targets / no default fails `target_selection_required` | s01, s02, s05 |
| API and CLI have identical JSON result | s03, s05 |
| Doctor uses probes only; never test/build scripts | s03, s06 |
| Old `project.yaml` / `.dev-hub/project.yaml` never read after cutover | s04, s06 |
| Hub self-test (`bin/pytest`, `test_run_canon`, `tier1_verify`) unchanged | s05, s06 |
| NFR-1 Resolver has no network/install/shell/target-script execution | s02, s03, s05 |
| NFR-2 All YAML boundaries use Pydantic `extra="forbid"` | s01, s02 |
| NFR-3 Root containment uses resolved `Path`, never prefix string checks | s01, s02 |
| NFR-4 Expected CLI failures preserve JSON output | s03 |
| NFR-5 Registry is local/immutable; no remote lookup | s02, s06 |
| NFR-6 Doctor probes have fixed low timeout and no secret output | s03 |
| NFR-7 argv boundaries never become `shlex.join` machine input | s02, s03, s05 |
| Independent Test FAIL path (YAML/classes alone is not evidence) | s02, s05 |
| Appetite cuts (init / version floors / custom profiles / pack phase syntax) | — cut_list, не шаги |
| Future consumer epic that executes capabilities | — Appetite cut; FR-014; no queue ID yet |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** roadmap).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).  
> Финальный `*-legacy-fallback-purge` в очереди с `sunset_inventory` + `grep_control`.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `_read_project_yaml_pack()` and untyped old YAML reads | A | `load_project_manifest().workflow_pack` | s04, s06 | no | FR-005/016; delete in-epic |
| tests asserting old config precedence (`project.yaml` > env) | A | typed manifest/migration negative tests | s04, s06 | no | rewrite in-epic |
| future consumer tool literals | A | resolver result | — | no | plan: delete when consumer migrates; FR-014 future epic; keep until that epic (documented keep in s05/s06) |
| `formula_render.py` default pytest / incident checks | A | hub self-test, not target command | s06 | no | keep, documented n/a (plan sunset A) |
| docs for project config at `project.yaml`/`.dev-hub/project.yaml` | B | root `dev-hub.project.yaml` | s04, s06 | no | FR-017 |
| treating `.dev-hub` as config directory | B | pointer-only `hub-link` semantics | s04, s06 | no | FR-004 |
| inferred profile from `Cargo.toml`/`pyproject.toml`/`package.json` | C | `targets.*.profile` | s02, s06 | yes | delete in-epic |
| assumed JS manager (silent npm/pnpm) | C | one lockfile/explicit override | s02, s06 | yes | delete in-epic |
| first/current/alphabetical target choice | C | explicit target/default | s02, s06 | yes | delete in-epic |
| new parser failure → old parser (`try new except old`) | C | typed diagnostic | s04, s06 | yes | delete in-epic |
| config docs teaching old locations | I | template + migration | s04, s06 | no | FR-017 |
| `.dev-hub` shown as YAML | I | one-line pointer explanation | s04, s06 | no | FR-004 |
| guidance to embed pytest/cargo/npm in generic consumer | I | fixed capability request | s05, s06 | no | rewrite in-epic where found |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-schema-manifest-containment-red.yaml](../yaml/steps/s01-schema-manifest-containment-red.yaml) | [s01…](../../implement/T-HUB-075-stack-profiles-rust-python-js/s01-schema-manifest-containment-red.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-bundled-registry-pure-resolver.yaml](../yaml/steps/s02-bundled-registry-pure-resolver.yaml) | [s02…](../../implement/T-HUB-075-stack-profiles-rust-python-js/s02-bundled-registry-pure-resolver.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-json-cli-doctor-no-script.yaml](../yaml/steps/s03-json-cli-doctor-no-script.yaml) | [s03…](../../implement/T-HUB-075-stack-profiles-rust-python-js/s03-json-cli-doctor-no-script.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-wire-workflow-pack-typed-manifest.yaml](../yaml/steps/s04-wire-workflow-pack-typed-manifest.yaml) | [s04…](../../implement/T-HUB-075-stack-profiles-rust-python-js/s04-wire-workflow-pack-typed-manifest.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-consumer-api-integration-no-lifecycle.yaml](../yaml/steps/s05-consumer-api-integration-no-lifecycle.yaml) | [s05…](../../implement/T-HUB-075-stack-profiles-rust-python-js/s05-consumer-api-integration-no-lifecycle.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-075-stack-profiles-rust-python-js/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** `no`  
**FORBIDDEN:** `yes (done)` без CR-ID · `no (CR-… closed)`
