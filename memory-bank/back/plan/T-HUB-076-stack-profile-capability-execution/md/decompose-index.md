# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-076-stack-profile-capability-execution  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — канон status  
**Дата:** 2026-09-07  
**Режим:** BACK DECOMPOSE

> Layout v2: machine index — `yaml/decompose-index.yaml`; shards — `yaml/steps/`. После DECOMPOSE IMPLEMENT загружает только текущий shard и machine index, а не этот документ и не полный plan.

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Measurable verification |
| :--- | :--- | :--- | :--- |
| FR-001 | Add strict typed models for a phase declaration, execution result and persisted evidence. Unknown fields fail; declaration accepts only capability enum, required target and optional selector under existing selector rules. | s01 | `test_stack_profile_execution_contract.py`; `test_epic_yaml_capability_checks.py` |
| FR-002 | Add a public executor that accepts only project root plus typed request/declaration, calls `resolve_capability()`, and runs only `resolution.argv` with `resolution.cwd`, `timeout_seconds` and `shell=False`. | s02 | `test_stack_profile_executor.py`; three-target integration |
| FR-003 | Executor never accepts raw command text, caller argv, cwd override, env override, profile override or timeout override; resolver failure means no subprocess call. | s01, s02, s06 | schema negatives; executor mock zero-spawn; Kind C scan |
| FR-004 | Execution emits `stack-capability-execution/v1` JSON with request fingerprint, resolution identity, start/end or duration, exit code/status, bounded output metadata and ordered diagnostics. No output body or secret-bearing environment is embedded in memory-bank YAML. | s01, s02, s03 | result-model, executor bounded-output and evidence serialization tests |
| FR-005 | `python -m loop.stack_profiles execute` is JSON-first and exposes the same typed result as API. Exit mapping distinguishes success, configuration/selection failure, unavailable/spawn failure, timeout, and delegated command failure. | s03 | execute CLI parity and exit-mapping tests |
| FR-006 | Extend decompose schema with explicit `capability_checks`; BACK/INTEG phase declarations are valid only with required named targets, allowed capability/selector pairing and no raw process fields. | s01, s04, s05 | schema negatives; armed-step parsing; finish rejection |
| FR-007 | `loop.context_loop.check_after()` finds declared checks for the current armed step, executes them before returning a green continuation, persists evidence under the role/epic/step execution artifact path and HALTs on any failed/missing/stale evidence. | s03, s04 | context-loop success/HALT integration tests |
| FR-008 | Finish/step validation recognises typed managed-project evidence and validates it against the current declaration fingerprint. Hub command evidence remains a separate, explicit contract and remains valid for hub-only work. | s03, s05, s06 | fingerprint mismatch tests; hub fixture zero-executor regression |
| FR-009 | Update BACK, INTEG and shared workflow instructions so managed project work declares and receives capability checks; instructions no longer prescribe Python-specific generic test commands as the managed-project default. | s06 | instruction inventory pytest + Kind I `rg` |
| FR-010 | Keep FRONT parent-only test authority. This epic may rewrite its vocabulary from manager literals to “managed frontend capability / approved scenario runner”, but it does not add profile `test.e2e` or execute browser tests through the capability executor. | s06 | instruction regression asserts explicit parent-only boundary and absence of E2E executor vocabulary |
| FR-011 | Do not change capability vocabulary, add `test.e2e`, broaden a profile, add a default target fallback, execute arbitrary commands, install packages or expose stream-output UI. | s01, s02, s04, s06 | schema/API negative tests; scoped inventory; out-of-scope assertions |
| FR-012 | Keep the existing hub test timeout/canon for testing the hub itself; only clarify its hub-only boundary. | s05, s06 | hub fixture regression and instruction inventory |
| US-001 | Workflow author declares Rust/Python/JS verification intent, not shell command, so runtime applies only registry-owned argv. | s01, s02, s04 | three-target exact argv/cwd and current-step execution test |
| US-002 | QA owner sees which named target and capability actually completed, so Python default cannot mask Rust/JS coverage. | s01, s03, s04, s05 | required-target, evidence identity and multi-evidence tests |
| US-003 | Operator gets JSON result and stable non-zero outcome on invalid manifest, spawn error, timeout or non-zero command. | s02, s03 | fake executable result matrix and CLI parity tests |
| US-004 | Hub maintainer keeps `bin/pytest` for hub tests without turning the Python suite into profile policy for external projects. | s05, s06 | existing hub fixture and zero profile-executor assertion |
| US-005 | Rule author supplies only executable machine path; workflow text does not require hardcoded pytest/cargo/npm commands. | s04, s06 | check-after wire test and instruction inventory |
| SC-001 | Explicit py/rs/web targets execute their exact resolved argv/cwd once each. | s02, s04 | temporary managed monorepo integration |
| SC-002 | No resolver/validation failure invokes a target subprocess. | s01, s02, s04 | schema/resolver failure mock asserts zero spawn |
| SC-003 | Failed, timed-out and non-zero command evidence blocks check-after. | s02, s04 | HALT matrix tests |
| SC-004 | Stale/wrong target/step evidence cannot satisfy finish. | s03, s05 | evidence mismatch finish tests |
| SC-005 | Hub validation stays distinct and has zero profile-executor calls. | s05, s06 | hub fixture regression |
| SC-006 | Managed instruction inventory contains no generic managed runner literals. | s06 | instruction inventory pytest and scoped `rg` |
| AC+ #1 | Three explicit target declarations execute exact resolver-owned argv/cwd and return PASS evidence. | s02, s04 | temporary monorepo integration |
| AC+ #2 | Omitted target stops decompose/check-after before target spawn. | s01, s04 | target-required negative tests |
| AC+ #3 | Failed execution blocks green continuation with typed diagnostic. | s02, s04 | fake child failure/HALT tests |
| AC+ #4 | Finish accepts only matching typed evidence, not copied/raw command proof. | s03, s05 | sidecar mismatch and tests-only rejection |
| AC+ #5 | Hub tests retain explicit valid canon and do not execute profiles. | s05 | hub fixtures |
| AC+ #6 | Rules describe the managed capability path and hub exception. | s06 | instruction inventory |
| AC− #1 | Raw command, argv, cwd, env, profile and timeout are never executable declaration inputs. | s01, s02 | Pydantic negatives + executor API surface |
| AC− #2 | No fallback to default target, hub command, npm/cargo/pytest literal or raw tests string after managed failure. | s02, s04, s05, s06 | no-spawn/HALT tests + Kind C scan |
| AC− #3 | No browser E2E capability or frontend test execution authority is added. | s06 | inventory test and out-of-scope scan |
| NFR safety | `shell=False`; resolver owns argv/cwd/deadline; bounded diagnostics; no secret/output body persistence. | s02, s03 | executor/evidence tests |
| NFR determinism | canonical fingerprint and atomic evidence path bind the declared check to its lifecycle owner. | s01, s03, s05 | fingerprint/atomic/mismatch tests |
| NFR fail-closed | invalid declaration, resolution, spawn, timeout, child failure, missing/stale proof all HALT/deny. | s01–s05 | negative matrix |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Strict declaration, result and evidence models | Plan delivery ladder 1; FR-001/006 | s01 |
| Resolver-to-subprocess execution boundary | Plan delivery ladder 2; FR-002/003/004 | s02 |
| JSON execute CLI and atomic sidecar protocol | Plan delivery ladder 3; FR-004/005 | s03 |
| Production phase wire and fail-closed continuation | Plan delivery ladder 4; FR-007 | s04 |
| Finish/schema evidence cutover and hub branch | Plan delivery ladder 5; FR-008/012 | s05 |
| A/B/C/I instruction and legacy authority purge | Plan delivery ladder 6; FR-009/010 | s06 |
| Add → wire → enforce → purge | behavior-first / spec-first replace | s01 → s04 → s05 → s06 |
| Temporary multi-target independent test | Plan Independent Test | s02, s04 |
| Hub regression without profile inference | Plan US-004 / TM-008 | s05, s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Explicit verification intent becomes the only input to managed execution. | s01, s02 |
| Python, Rust and JavaScript execute only named resolver targets with auditable typed outcomes. | s02, s03 |
| An operator receives stable JSON and status without leaking output or accepting arbitrary process controls. | s02, s03 |
| A workflow phase cannot turn green while its current managed checks are missing, invalid, failed or stale. | s04, s05 |
| Hub tests remain a separate valid contract rather than a fallback profile policy. | s05, s06 |
| Rules stop teaching generic language-specific commands as managed workflow truth. | s06 |
| FRONT stays parent-only; no browser/E2E capability is added. | s06 |
| Appetite cut: no custom profiles, version floors, install, streaming, remediation or test.e2e. | s01, s02, s04, s06 |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Проверка |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `tests_format.py::is_allowed_test_command` as generic workflow-process gate | A | Explicit hub-only validator plus typed capability/evidence validator | s05, s06 | no | `rg` caller inventory + managed evidence tests |
| `tests_format.py::extract_test_commands_from_yaml_tests` as universal execution evidence | A | Hub-only extraction plus fingerprint matcher | s05, s06 | no | `rg` + raw tests-only rejection |
| `test_run_canon.py::ALLOWED_TEST_PREFIXES` as managed-target authority | A | Resolver-owned executor | s05, s06 | no | `rg` + no-spawn test |
| No profile executor/evidence module | A | `loop.stack_profiles.execution` and `evidence` | n/a — new surface | no | s02/s03 API and sidecar tests |
| `context_loop.py` check-after ignores declared checks | A | current-step execution/HALT gate | s04 | yes | context-loop integration/HALT matrix |
| resolve CLI is only operational profile CLI | B | add execute CLI; keep resolve as distinct read-only operation | n/a — not a replacement | no | CLI parity test |
| check-after green path without managed execution | B | execute/persist declared checks before continuation | s04, s06 | yes | current-step wire test + B inventory |
| `format_spec_lines` assumes loop runs YAML shell strings | B | typed managed evidence instruction and explicit hub branch | s05, s06 | yes | validator tests + `rg` |
| invalid declaration falls back to command prose | C | fail-closed diagnostic/no subprocess | s01, s04, s06 | yes | target-required/no-spawn tests |
| omitted managed target falls back to default/current directory | C | required target diagnostic | s01, s04, s06 | yes | schema/phase test |
| unavailable result can be replaced by PASS prose | C | fingerprinted evidence at finish | s03, s05, s06 | yes | mismatch tests |
| failed target becomes hub self-test/retry | C | typed failure/HALT | s02, s04, s06 | yes | non-zero/HALT and Kind C scan |
| shared test-timeout generic managed pytest wording | I | separate hub runner and managed capability contract | s06 | no | instruction inventory |
| BACK generic managed pytest wording | I | declaration/evidence plus hub exception | s06 | no | instruction inventory |
| INTEG generic managed pytest wording | I | capability-driven managed checks | s06 | no | instruction inventory |
| Claude role-command universal pytest wording | I | runtime parity branch by hub versus managed project | s06 | no | instruction inventory |

## Очередь шагов

| step_id | title & shard | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| s01 | [Strict capability execution declaration, result, and fingerprint contract](../yaml/steps/s01-capability-execution-contract.yaml) | no | yes | BACK IMPLEMENT | pending |
| s02 | [Resolver-owned argv executor reports bounded typed process outcomes](../yaml/steps/s02-resolver-owned-executor.yaml) | no | yes | BACK IMPLEMENT | pending |
| s03 | [JSON execute CLI persists target-bound capability evidence atomically](../yaml/steps/s03-execute-cli-and-evidence.yaml) | no | yes | BACK IMPLEMENT | pending |
| s04 | [check-after executes current-step checks and HALTs without valid evidence](../yaml/steps/s04-check-after-capability-enforcement.yaml) | no | yes | BACK IMPLEMENT | pending |
| s05 | [Finish validation distinguishes managed capability evidence from hub tests](../yaml/steps/s05-finish-managed-evidence-validation.yaml) | no | yes | BACK IMPLEMENT | pending |
| s06 | [Purge generic managed-test command authority and stale workflow instruction paths](../yaml/steps/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |

**CREATIVE verify:** no CR expected: the plan fixes an explicit resolver/executor/evidence boundary and has no unresolved architectural choice.  
**Next mode:** `BACK ANALYZE T-HUB-076-stack-profile-capability-execution` in a new chat. IMPLEMENT is prohibited until the ANALYZE artifact reports `critical_count: 0`.

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Strict capability execution declaration, result, and fingerprint contract · [yaml](s01-capability-execution-contract.yaml) | BACK IMPLEMENT | completed |
| **s02** | Resolver-owned argv executor reports bounded typed process outcomes · [yaml](s02-resolver-owned-executor.yaml) | BACK IMPLEMENT | completed |
| **s03** | JSON execute CLI persists target-bound capability evidence atomically · [yaml](s03-execute-cli-and-evidence.yaml) | BACK IMPLEMENT | completed |
| **s04** | check-after executes current-step checks and HALTs without valid evidence · [yaml](s04-check-after-capability-enforcement.yaml) | BACK IMPLEMENT | completed |
| **s05** | Finish validation distinguishes managed capability evidence from hub tests · [yaml](s05-finish-managed-evidence-validation.yaml) | BACK IMPLEMENT | completed |
| **s06** | Purge generic managed-test command authority and stale workflow instruction paths · [yaml](s06-legacy-fallback-purge.yaml) | BACK IMPLEMENT | completed |