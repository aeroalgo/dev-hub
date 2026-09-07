# [T-HUB-080 | workflow-capability-instruction-parity] PLAN

**Дата:** 2026-09-07
**Режим:** BACK PLAN
**Уровень:** L3
**Статус:** active
**Clarify:** Phase 0 skipped — taxonomy clear: пользователь назвал конкретную проблему (остаточные прямые runner-вызовы после 076) и требуемое поведение (ветка hub против managed capability); дополнительный продуктовый вопрос не меняет границу эпика.
**Prompt:** [md/prompt.md](prompt.md) — outcome SoT, не HOW.
**Deps:** hard T-HUB-076 (capability execution contract and managed evidence; already completed, so `roadmap-merge` removes it from the active-row dependency list); no hard dependency on T-HUB-077 (receipt integrity is orthogonal and remains unchanged).
**Batch:** `claude-session-audit-20260907`
**Skills:** writing-plans · python-testing-patterns · architecture-patterns (Eng review).
**Источник:** пользовательский запрос о workflow после T-HUB-076/077; current instruction inventory; `harness/cursor/rules/**`; `harness/claude/**`; `harness/skills/role-command/SKILL.md`; `harness/instructions/main.md`; `loop/tests/test_stack_profile_instruction_inventory.py`.

## Контекст

T-HUB-076 ввёл исполнимую границу для managed-проектов: автор объявляет `capability_checks`, runtime резолвит named target, выполняет resolver-owned argv и сохраняет typed evidence. Для самого dev-hub сохранён отдельный hub runner (`bin/pytest` с внешним timeout-контрактом). Это разделение корректно описано в shared `test-timeout` и частично в role core/gates.

Однако предыдущий purge s06 проверил только перечисленные core/lean файлы и не сделал полного corpus inventory активных workflow. В результате в источнике инструкций остались строки, которые читаются как универсальный рецепт:

| Поверхность | Фактическая формулировка | Почему это drift |
|---|---|---|
| `harness/cursor/rules/back_developer/workflow-implement.mdc:39` | `TDD targeted → code → green (bin/pytest)` | Нет условия hub-only; managed агент получает прямой runner вместо declaration/evidence. |
| `harness/cursor/rules/back_developer/workflow-task.mdc:17` | `TDD red → green: .venv/bin/pytest` | Вне managed branch, конфликтует с capability path. |
| `harness/cursor/rules/back_developer/workflow-bugfix.mdc:13` | `regression red → fix → green (.venv/bin/pytest)` | BUGFIX может быть запущен в managed root, но инструкция не различает root type. |
| `harness/cursor/rules/back_developer/workflow-qa.mdc:20` | `Full pytest ... bin/pytest` | QA не имеет managed alternative в самом mode workflow, хотя lean gate уже её знает. |
| `harness/cursor/rules/integration_developer/workflow-implement.mdc:29,33` | `targeted .venv/bin/pytest` / `pytest HTTP outcome` | INTEG branch смешивает hub HTTP tests с managed capability declaration. |
| `harness/cursor/rules/integration_developer/workflow-qa.mdc:12` | `full bin/pytest` | Managed QA branch отсутствует в workflow text. |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/{implement,task,bugfix}.mdc` | `.venv/bin/pytest` без hub condition | Gates themselves can reintroduce the old recipe after 076. |
| `harness/claude/rules/context-economy-cc.md:55` | generic `.venv/bin/pytest` anti-bloat recipe | Claude Code can receive contradictory instruction before role workflow. |
| `harness/skills/role-command/SKILL.md:10` | generic `pytest` runner text | `.agents/skills` points here; it is a stale runtime-specific copy, unlike updated `harness/claude/skills/role-command/SKILL.md`. |
| templates and entrypoint docs | direct `.venv/bin/pytest` examples | New shards/templates can teach the same drift even after rule files are fixed. |

The root `.cursor/rules` path is a symlink to `harness/cursor/rules`; `.claude/rules`, `.claude/skills`, `.claude/instructions` are symlinked runtime views. Therefore the canonical write surface is `harness/**`, while the plan must test both source and runtime-visible paths. `AGENTS.md` and `CLAUDE.md` are generated runtime entrypoints; their source is `harness/instructions/main.md`, but the current sync checker deliberately accepts a generated header without comparing the body, so the inventory must not assume that `runtime-sync --check` alone proves semantic parity.

T-HUB-077 does not fix this. Its source of truth is verifier receipt provenance and fail-closed finish enforcement; changing runner wording is an instruction-contract follow-up to T-HUB-076. The 080 plan must not change receipt authority, stack-profile capabilities, executor policy, or `test.e2e` vocabulary.

## Goal

Make the hub-versus-managed test decision explicit and consistent at every active workflow instruction surface. A direct runner literal is valid only inside a clearly marked hub-only branch or a negative statement; managed work must name `capability_checks` and typed execution evidence. The rule is enforced by a comprehensive inventory test rather than by a hand-maintained list of seven files.

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Branch-qualified workflow test policy | `vertical_slice` | Active BACK/INTEG/FRONT mode rules and `_lean` gates consumed by the role router and parent agent | A managed branch without `capability_checks`/evidence is rejected; a direct runner literal outside explicit hub/negative context fails instruction inventory | Given a corpus containing a stale unqualified line, inventory test fails; after rewrite, hub fixture remains valid and managed fixture requires declaration/evidence | `n/a` |
| Cross-runtime instruction parity | `vertical_slice` | `harness/**` canonical source → symlinked `.cursor/.claude/.agents` views and generated `CLAUDE.md`/`AGENTS.md` entrypoints | Source and runtime-visible copies expose the same branch semantics; semantic drift is non-zero in inventory/sync verification | Given source and destination copies with one stale runner sentence, parity test reports the exact path and branch violation | `n/a` |

## Technology axiom (replace-not-wrap)

| Выбор | Единственный machine/input SoT | FORBIDDEN после эпика |
|---|---|---|
| Managed verification instruction | `capability_checks` declaration + stack-profile execution evidence | `pytest`, `cargo`, `npm`, raw `tests:` or arbitrary command as an implicit managed default |
| Hub verification instruction | Explicit `hub-only` / `dev-hub` context with the canonical `bin/pytest` runner and timeout contract | Applying hub runner commands to an external managed project or hiding the context condition in a generic sentence |
| Instruction corpus | Canonical `harness/cursor`, `harness/claude`, `harness/skills`, `harness/instructions`, and templates; symlinked runtime views are projections | A short allowlist presented as a complete inventory; editing generated runtime destinations as an independent source |
| Inventory enforcement | Executable Python test with corpus discovery, semantic branch checks, and parity assertions | Presence-only `assert "managed" in content`, manual grep of one file, or green test that skips stale workflow files |

The axiom deliberately keeps direct `bin/pytest` for dev-hub tests. The replacement is not a global deletion of the word `pytest`; it is the removal of unqualified managed authority and the conversion of every ambiguous action sentence into a two-branch contract.

## Продуктовая спека (WHAT)

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|---|---|---|
| 1 | **Reframe:** какую реальную проблему решаем? | Агент в managed root видит несколько conflicting recipes и может выбрать Python runner, даже когда target — Rust/JS. | Исправляем не лексику, а decision boundary: root classification → hub или capability evidence. |
| 2 | **Narrowest wedge:** какой минимальный вариант проверит гипотезу? | Скан всех активных instruction/workflow surfaces с проверкой контекста строки и branch markers. | Один executable inventory test должен ловить пропущенный `workflow-*.mdc`, stale skill и template. |
| 3 | **Pre-mortem:** почему план может провалиться? | Можно заменить строки в `harness`, но оставить stale runtime copy или generated entrypoint; можно также удалить допустимый hub exception. | Ввести source/runtime parity checks, явный allowlist допустимых hub references и негативных fixtures. |
| 4 | **Distribution/Adoption:** кто использует результат? | BACK/INTEG/FRONT authors, parent agents, Claude/Codex role-command loaders и scaffolded shard authors. | Включить mode workflows, lean gates, role skills, templates и main entrypoint source в один corpus. |
| 5 | **Technical leverage:** что переиспользуем? | `shared/test-timeout.mdc` уже содержит корректный semantic contract; 076 evidence validator уже разделяет hub tests и managed evidence. | Не вводить новый runner/API; сделать остальные поверхности ссылочными/ветвящимися и расширить существующий inventory test. |
| 6 | **Appetite check:** стоит ли scope ресурсов? | Да, это L3 docs/infra cutover на 2 дня; код executor/registry не меняется. | Cut list: cosmetic prose, archive/history docs, new capability types, browser executor, sync redesign beyond semantic check. |

### User Stories

| # | Story | Priority | Independent Test |
|---|---|---|---|
| US-001 | Как автор BACK/INTEG workflow, я хочу сразу видеть hub-only и managed branches, чтобы не прописать Python runner для внешнего проекта. | P0 | Corpus scan finds no action sentence with a direct runner literal unless it carries an explicit hub/negative marker and the file carries managed capability guidance. |
| US-002 | Как QA owner, я хочу, чтобы full/targeted checks в каждом mode workflow приводили к capability evidence для managed roots и сохраняли hub full/targeted exception. | P0 | Synthetic managed rule fixture with `bin/pytest` only fails; fixture with `capability_checks` and evidence markers passes; hub fixture passes. |
| US-003 | Как Codex/Claude operator, я хочу одинаковые правила из `.agents` и `.claude`, чтобы runtime не выбирал разные execution policies. | P1 | Compare semantic markers and stale-literal report across `harness/skills`, `harness/claude/skills`, `harness/instructions`, `AGENTS.md`, and `CLAUDE.md`. |
| US-004 | Как автор нового shard/template, я хочу, чтобы пример `tests:` не обучал managed fallback, даже если он копируется из template. | P1 | Template corpus scan rejects unqualified executable examples and accepts hub-only/capability alternatives. |

#### Acceptance Scenarios — US-001

- **Given:** BACK IMPLEMENT contains a line `green (bin/pytest)` without a scope marker.
- **When:** instruction inventory runs over active source files.
- **Then:** the test reports file, line, mode and required rewrite; the workflow cannot be considered converged.

- **Given:** the rewritten line says `hub-only: bin/pytest` and separately says managed checks use `capability_checks` plus evidence.
- **When:** the inventory runs.
- **Then:** the line is accepted and the hub/managed branch contract is recorded as covered.

#### Acceptance Scenarios — US-002

- **Given:** an external project has Python, Rust and JavaScript targets but no hub identity.
- **When:** BACK QA or INTEG QA is selected.
- **Then:** the instruction points to `test.full`/other named capabilities and typed evidence; it does not prescribe `bin/pytest`.

- **Given:** the repository under test is dev-hub itself.
- **When:** a hub QA fixture is evaluated.
- **Then:** `bin/pytest -q --tb=line` remains valid under the explicit hub exception.

#### Acceptance Scenarios — US-003

- **Given:** `.agents/skills/role-command/SKILL.md` and Claude skill copies differ in branch semantics.
- **When:** parity test runs.
- **Then:** it reports the stale copy and fails until both runtime variants carry the same hub/managed policy.

#### Acceptance Scenarios — US-004

- **Given:** a decompose, implement, QA, security, refactor, or integration template contains a direct runner example.
- **When:** a new shard author reads the template and the inventory scans it.
- **Then:** the example is either explicitly hub-only or accompanied by the managed capability form; ambiguous examples fail.

### Functional Requirements (FR-###)

- **FR-001:** The active instruction corpus MUST include every non-archive `workflow-*.mdc`, relevant `_lean/*.mdc`, role core, shared test contract, role-command skill copy, instruction entrypoint source, and executable shard template that can prescribe tests.
- **FR-002:** Every direct `pytest`, `cargo`, `npm`, `vitest`, or raw `tests:` execution recipe in an action context MUST be explicitly scoped to hub/self-test or be replaced with `capability_checks` plus typed evidence language.
- **FR-003:** BACK IMPLEMENT, TASK, BUGFIX, and QA mode workflows and gates MUST distinguish hub targeted/full checks from managed targeted/full capability checks without relying on a generic Python default.
- **FR-004:** INTEG IMPLEMENT and QA, integration core/lean gates, and the HTTP scenario wording MUST distinguish hub pytest HTTP tests from managed capability checks; frontend browser execution remains parent-only and outside the capability executor.
- **FR-005:** FRONT core runner wording MUST carry the same hub-only condition and managed capability reference while retaining the parent-only Vitest/RTL/Playwright authority.
- **FR-006:** `harness/skills/role-command/SKILL.md` MUST be brought to semantic parity with `harness/claude/skills/role-command/SKILL.md`; the `.agents/skills` symlink must expose the corrected text.
- **FR-007:** `harness/instructions/main.md` MUST describe both runtime entrypoint selection and the hub-versus-managed test policy; generated `AGENTS.md`/`CLAUDE.md` destinations MUST be checked for the same policy markers.
- **FR-008:** Templates that create or validate plan/decompose/implement/QA/security/refactor/integration artifacts MUST not contain an unqualified executable managed runner example; examples MUST identify hub-only or capability evidence.
- **FR-009:** The instruction inventory test MUST detect omitted active files by glob/discovery, report exact stale lines, accept negative statements and archives only under documented exclusions, and preserve hub exception tests.
- **FR-010:** The epic MUST not alter stack-profile capability vocabulary, resolver/executor/evidence code, receipt provenance, `test.e2e`, arbitrary shell execution, package installation, or frontend parent-only authority.

### Success Criteria

| ID | Измеримый результат | Проверка / источник | Type |
|---|---|---|---|
| SC-001 | 0 unqualified managed runner action lines in the active workflow corpus. | `test_stack_profile_instruction_inventory.py` semantic scan plus scoped `rg`. | enforce |
| SC-002 | 100% of BACK/INTEG mode files that mention tests contain both explicit hub exception and managed capability guidance, or an explicit read-only/negative reason. | Corpus inventory report grouped by mode. | outcome |
| SC-003 | Both role-command skill variants carry equivalent hub/managed markers and no stale generic runner sentence. | parity test over `harness/skills` and `harness/claude/skills`. | regression |
| SC-004 | All executable templates that show a test command identify hub-only scope; managed examples use declaration/evidence language. | template inventory test. | enforce |
| SC-005 | Hub test fixtures remain accepted and managed tests-only proof remains rejected. | existing 076 evidence/format tests plus new inventory regression. | regression |
| SC-006 | Generated runtime entrypoint destinations contain the branch policy after sync check/apply, with no manual divergent body accepted as proof. | runtime-sync fixture and entrypoint semantic check. | parity |
| SC-007 | FRONT parent-only rule remains present and no `test.e2e` capability is introduced. | explicit assertions in inventory test and existing capability enum test. | safety |
| SC-008 | Full hub suite is green after instruction rewrites. | `bin/pytest -q --tb=line` from repository root; this command tests dev-hub itself. | regression |

### Assumptions

- T-HUB-076 is the authority for managed capability execution and evidence semantics; this epic only fixes instruction coverage and its enforcement test.
- `harness/**` is the canonical editable source for symlinked `.cursor`, `.claude`, and `.agents` views. Generated `AGENTS.md`/`CLAUDE.md` remain runtime projections and are not independent sources.
- Direct runner references in code tests, negative statements, archive/history, and stack-profile registry data are not managed workflow authority, but tests must classify them rather than deleting them blindly.
- A managed project is identified by the existing profile/manifest contract; this plan does not infer managed status from the presence of Python or from a directory name.
- Frontend Playwright/Vitest execution remains parent-only. No subagent is authorized to run frontend tests as part of this docs parity epic.

### Clarifications

- Session: 2026-09-07, `BACK PLAN`; no separate Q→A artifact because the request is a narrow, explicit follow-up to the observed 076 instruction gap.
- Decision: create a new epic instead of rewriting 076/077 plans or their completed/decomposed artifacts. 080 depends on 076 and leaves 077 receipt integrity untouched.
- Decision: direct `bin/pytest` is preserved only with an explicit dev-hub/hub-only condition; the literal itself is not globally banned.

## AC

1. Every active BACK/INTEG/FRONT/shared test decision point states the hub-only runner branch and the managed `capability_checks`/typed-evidence branch, or explicitly states that the mode is read-only and does not execute tests.
2. `BACK IMPLEMENT`, `BACK TASK`, `BACK BUGFIX`, `BACK QA`, `INTEG IMPLEMENT`, and `INTEG QA` no longer present `.venv/bin/pytest`, `bin/pytest`, or `pytest HTTP outcome` as an unconditional managed recipe.
3. The stale `harness/skills/role-command/SKILL.md` copy is rewritten; Claude and Codex role-command copies carry equivalent policy markers.
4. The inventory discovers all active workflow files and templates rather than relying on the seven-file 076 allowlist; adding a new active workflow file with an ambiguous runner line makes the test fail.
5. Hub-only tests remain valid, including `bin/pytest -q --tb=line` for full hub QA and targeted hub checks from repository root with the shared timeout contract.
6. Managed test execution is described only through named capability declarations and execution evidence; no fallback to hub pytest, raw tests strings, default target, cargo, npm, or Python command is taught.
7. Runtime entrypoint source and runtime-visible copies retain the same policy, and parity checks report stale destinations instead of silently accepting a generated header.
8. FRONT parent-only test authority remains explicit; this epic introduces no `test.e2e` capability or browser execution through the stack-profile executor.

### AC−

1. No action sentence in an active managed-capable workflow can be interpreted as “run pytest” without a hub-only marker.
2. No managed branch uses a generic `pytest`, `.venv/bin/pytest`, `bin/pytest`, `cargo test`, `npm test`, `npm run test`, raw shell string, or copied `tests:` result as its proof.
3. No broad regex deletes valid negative text such as “no fallback to pytest” or valid hub-only examples; classification must be context-aware.
4. No workflow file is excluded merely because it was absent from 076 s06’s original allowlist; discovery covers active `workflow-*.mdc`, `_lean`, core, skills, entrypoint and template surfaces.
5. No generated `AGENTS.md`/`CLAUDE.md` body is treated as a separate source that can diverge from `harness/instructions/main.md`.
6. No `test.e2e`, browser capability, arbitrary command, installation, profile extension, receipt mutation, or executor change is smuggled into the epic.
7. No obsolete test is made green by restoring the generic managed command authority removed by 076.

## Техника / архитектура (HOW)

### Source and runtime topology

```text
harness/cursor/rules/** ─┐
harness/claude/rules/** ─┼─> canonical instruction corpus test
harness/skills/** ──────┤          │
harness/claude/skills/**┤          ├─> branch-qualified workflow policy
harness/cursor/templates/**          │
harness/instructions/main.md ───────┘
          │
          ├─ symlinked views: .cursor/rules, .claude/rules, .claude/skills, .agents/skills
          └─ generated runtime entrypoints: CLAUDE.md / AGENTS.md

role router / parent
          ├─ hub root → explicit bin/pytest (hub timeout contract)
          └─ managed root → capability_checks → resolver/evidence (076 SoT)
```

The test is a semantic guard, not a second execution policy. `shared/test-timeout.mdc` remains the canonical wording for timeout mechanics; mode workflows either reference that contract or repeat its two branches exactly. The test never executes an external managed command; all pytest commands in the QA matrix below are hub tests of dev-hub’s instruction/runtime behavior.

### Ownership and file layout

| Surface / owner | Files in scope | Planned responsibility |
|---|---|---|
| Corpus contract / tests | `loop/tests/test_stack_profile_instruction_inventory.py` | Discover files, classify direct runner lines, assert branch markers, preserve hub and FRONT boundaries, report exact violations. Keep helper logic in this test module unless a separately named helper is required by a concrete readability failure. |
| BACK modes | `harness/cursor/rules/back_developer/workflow-implement.mdc`; `workflow-task.mdc`; `workflow-bugfix.mdc`; `workflow-qa.mdc`; `mainrule-core.mdc`; `_lean/implement.mdc`; `_lean/task.mdc`; `_lean/bugfix.mdc`; `_lean/qa.mdc` | Rewrite action lines with explicit hub/managed branches; leave negative/forbidden checks intact; keep QA full-suite distinction. |
| INTEG modes | `harness/cursor/rules/integration_developer/workflow-implement.mdc`; `workflow-qa.mdc`; `mainrule-core.mdc`; `_lean/implement.mdc`; `_lean/bugfix.mdc`; `_lean/qa.mdc` | Separate hub HTTP pytest scenario from managed capability evidence; preserve UI scenario and parent-only browser rule. |
| FRONT/shared contract | `harness/cursor/rules/front_developer/mainrule-core.mdc`; `harness/cursor/rules/shared/test-timeout.mdc`; `harness/claude/rules/context-economy-cc.md` | Make generic runner language branch-qualified; shared timeout remains one canonical policy. |
| Runtime role skills | `harness/skills/role-command/SKILL.md`; `harness/claude/skills/role-command/SKILL.md` | Bring Codex `.agents` and Claude role command instructions to semantic parity without merging runtime-specific tool mechanics. |
| Entrypoint source/projections | `harness/instructions/main.md`; `AGENTS.md`; `CLAUDE.md`; `harness/manifest.yaml`; `loop/runtime_materializers/sync.py` only if needed to make semantic drift observable | State root classification and check generated destination policy; do not hand-edit projections as a separate source. |
| Artifact templates | `harness/cursor/templates/plan.md`; `decompose/epic-step.yaml`; `decompose/legacy-purge-step.yaml`; `implement/epic-step.yaml`; `qa/epic-step.yaml`; `integration-plan.md`; `refactor/epic-step.yaml`; `security/epic-step.yaml`; `finish-doc-router.md` | Mark direct examples hub-only or replace managed examples with `capability_checks`/evidence; retain executable format requirements. |
| Hub operator docs | `loop/WORKFLOW.md`; `loop/README.md` | Keep direct hub commands but label them as dev-hub self-tests so they cannot be copied as managed policy. |

### Semantic classification contract

| Line/context | Accept | Reject |
|---|---|---|
| Hub action | `Hub/dev-hub self-tests: bin/pytest ...` or the shared timeout form | `bin/pytest ...` in a mixed/managed-capable sentence with no hub marker |
| Managed action | `capability_checks: [test.targeted/test.full/...]; typed execution evidence` | Any raw runner literal, default target, or prose PASS as the managed action |
| Negative policy | `FORBIDDEN: fallback to pytest` / `no generic runner` | A negative phrase that still instructs the agent to execute the command |
| Read-only mode | `ANALYZE does not run pytest/vitest/...` | A read-only file that accidentally contains a positive runner recipe |
| Template | Separate `Hub example` and `Managed example` blocks | One undifferentiated `.venv/bin/pytest` example presented as universal |
| Frontend | `Playwright/Vitest — parent only`; managed API capability where applicable | `test.e2e` profile addition or subagent browser authority |

### Runtime-sync treatment

The plan does not redesign `ManifestSync`. First, update `harness/instructions/main.md` and run the existing materializer to observe destination behavior. If the generated-header bypass prevents a semantic check, add the smallest test-only/diagnostic seam that compares required branch markers without replacing the documented overlay policy. Any production sync change must preserve user overlays, be covered by `loop/tests/test_runtime_sync_check.py`, and be listed in the final sunset scan. A generated destination is never manually edited to hide source drift.

## Eng review spine

### Data flow

```text
[workflow author / parent]
        |
        v
[role router loads mode workflow + lean gate]
        |
        +--> [hub root explicitly identified] ------> [bin/pytest hub test]
        |
        +--> [managed root explicitly identified] -> [capability_checks declaration]
                                                   -> [076 executor/evidence SoT]
        |
        v
[instruction inventory + runtime parity test]
        |
        +--> pass: branch-qualified policy is consumable
        +--> fail: exact stale path/line blocks convergence
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|---|---|---|---|---|
| BACK workflow → managed project | unconditional `bin/pytest` survives | semantic corpus scan | fail inventory with path/line and required capability wording | TM-080-01 |
| BACK lean gate → managed project | `.venv/bin/pytest` reintroduced in `_lean` | discovered gate scan | reject stale gate before it can be used for IMPLEMENT/TASK/BUGFIX | TM-080-02 |
| INTEG scenario → managed API | `pytest HTTP outcome` interpreted as universal | action-context classifier | require hub-only marker or managed capability declaration; preserve parent browser boundary | TM-080-03 |
| QA workflow → managed full suite | full hub command appears without root condition | mode coverage assertion | fail QA instruction parity; no false managed PASS | TM-080-04 |
| Codex skill → Claude skill | one copy has generic runner text | semantic parity comparison | report stale runtime-specific copy; update canonical source | TM-080-05 |
| harness source → generated entrypoint | destination retains old body under generated header | required marker check + sync fixture | report destination drift; regenerate from source, do not hand-edit | TM-080-06 |
| template → newly scaffolded shard | direct command example copied as managed recipe | template corpus scan | fail template gate before new shard is accepted | TM-080-07 |
| cleanup → hub exception | broad replacement deletes valid hub runner contract | hub fixture and allowlist assertions | fail regression; restore explicit hub-only text, not generic authority | TM-080-08 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|---|---:|---|
| Data flow complete | 5 | Source, router, hub/managed branches, evidence and inventory are connected. |
| Failure coverage | 5 | Stale workflow, stale lean, runtime copy, template and over-broad purge all have tests. |
| Testability | 5 | Corpus fixtures are local; no external managed command, browser, network or package install is needed. |

## Replacement / sunset (brownfield)

This is an instruction-contract cutover. The replacement is not deletion of every `pytest` token; it is deletion of ambiguous authority and replacement with explicit branch semantics. All A/B/C/I rows use `delete in-epic` unless the row is explicitly marked `n/a`.

### A. Code / tests

| Устаревает (path / symbol) | Замена | Policy |
|---|---|---|
| `loop/tests/test_stack_profile_instruction_inventory.py::test_instruction_inventory_has_no_generic_managed_test_runner` — seven-file presence check | Corpus discovery + action-context semantic inventory with exact stale-line diagnostics | delete in-epic |
| `loop/tests/test_stack_profile_instruction_inventory.py::test_instruction_inventory_retains_explicit_hub_exception` — fixed four-file allowlist | Discovered hub exception assertions over all relevant mode/core/template surfaces | delete in-epic |
| `loop/tests/test_stack_profile_instruction_inventory.py::test_sunset_a_b_c_i_scans_have_no_live_legacy_authority` — partial symbol checks only | Full Kind I scan plus existing 076 hub/managed validator tests | delete in-epic |
| Obsolete assertions that treat “managed” presence as sufficient while allowing an unqualified action line | Assertions on branch semantics and no generic managed authority | delete in-epic |

### B. Entrypoints / deploy

| Устаревает (entrypoint) | Замена | Policy |
|---|---|---|
| n/a — this epic does not replace a compose service, Dockerfile CMD, deploy process, or product CLI | n/a | n/a |

### C. Fallbacks / soft-fail

| Устаревает (pattern / default) | Замена (fail-closed) | Policy |
|---|---|---|
| Mixed workflow sentence that silently defaults managed verification to `bin/pytest` / `.venv/bin/pytest` | Explicit managed `capability_checks` + typed evidence branch; missing branch is inventory failure | delete in-epic |
| `pytest HTTP outcome` or raw `tests:` prose presented without hub scope | Hub-only scenario label or managed evidence contract; no command fallback | delete in-epic |
| “Python tests” in runtime entrypoint text without root classification | “dev-hub self-tests” versus “managed project capability checks” | delete in-epic |
| Generated-header bypass treated as proof that a runtime destination matches source semantics | Required-marker semantic check over source and destination; preserve overlay behavior but fail stale policy | delete in-epic |

### I. Instruction surfaces

| Устаревает (path / phrase) | Замена (инструкция нового SoT) | Policy |
|---|---|---|
| `harness/cursor/rules/back_developer/workflow-implement.mdc:39` direct `green (bin/pytest)` | `hub-only` branch plus managed capability/evidence branch | delete in-epic |
| `harness/cursor/rules/back_developer/workflow-task.mdc:17` direct `.venv/bin/pytest` | Branch-qualified targeted hub test versus `test.targeted` capability | delete in-epic |
| `harness/cursor/rules/back_developer/workflow-bugfix.mdc:13` direct regression `.venv/bin/pytest` | Branch-qualified reproduction/regression policy | delete in-epic |
| `harness/cursor/rules/back_developer/workflow-qa.mdc:20` unconditional full `bin/pytest` | Hub full suite row and managed full capability row | delete in-epic |
| `harness/cursor/rules/back_developer/mainrule-core.mdc:12,20–26` any generic runner sentence | Keep hub exception, attach managed branch to every action context | delete in-epic |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/implement.mdc:24` | `hub: targeted bin/pytest` or `managed: capability_checks` | delete in-epic |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/task.mdc:14` | Same branch contract for ad-hoc tasks | delete in-epic |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/bugfix.mdc:16` | Same branch contract for regression tests | delete in-epic |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/qa.mdc:35,41` generic pytest coverage wording | Hub-only coverage runner or managed capability coverage evidence | delete in-epic |
| `harness/cursor/rules/integration_developer/workflow-implement.mdc:29,33` direct targeted pytest / HTTP outcome | Hub API scenario versus managed capability declaration; Playwright remains parent-only | delete in-epic |
| `harness/cursor/rules/integration_developer/workflow-qa.mdc:12` unconditional full hub pytest | Hub full suite and managed full capability alternatives | delete in-epic |
| `harness/cursor/rules/integration_developer/mainrule-core.mdc:15,21–24,36` mixed pytest scenario text | Branch-qualified hub API test and managed capability wording | delete in-epic |
| `harness/cursor/rules/integration_developer/isolation_rules/_lean/implement.mdc:23–24` | Keep explicit hub/managed alternatives and remove bare HTTP pytest action | delete in-epic |
| `harness/cursor/rules/integration_developer/isolation_rules/_lean/bugfix.mdc:13` | Hub HTTP scenario versus managed evidence | delete in-epic |
| `harness/cursor/rules/integration_developer/isolation_rules/_lean/qa.mdc:15` | Hub full suite versus managed full capability checks | delete in-epic |
| `harness/cursor/rules/front_developer/mainrule-core.mdc:9` generic pytest runner | Explicit hub-only note plus managed capability reference; preserve parent-only frontend tests | delete in-epic |
| `harness/cursor/rules/shared/test-timeout.mdc` examples only where scope is ambiguous | Keep canonical examples but label hub-only and managed branches unambiguously | delete in-epic |
| `harness/claude/rules/context-economy-cc.md:55` generic `.venv/bin/pytest` anti-bloat recipe | Hub-only command or managed capability evidence wording | delete in-epic |
| `harness/skills/role-command/SKILL.md:10` stale generic pytest text | Runtime-neutral hub/managed branch matching Claude role skill | delete in-epic |
| `harness/claude/skills/role-command/SKILL.md:10` parity drift if wording differs after rewrite | Same semantic policy with Claude-specific tool mechanics retained | delete in-epic |
| `harness/instructions/main.md:41` unqualified “Python tests” sentence | Explicit dev-hub self-test versus managed capability statement | delete in-epic |
| `harness/cursor/templates/{plan.md,decompose/epic-step.yaml,decompose/legacy-purge-step.yaml,implement/epic-step.yaml,qa/epic-step.yaml,integration-plan.md,refactor/epic-step.yaml,security/epic-step.yaml,finish-doc-router.md}` direct examples lacking scope | Scoped hub examples and capability/evidence managed examples | delete in-epic |
| `loop/WORKFLOW.md` and `loop/README.md` direct test commands without “dev-hub self-test” label | Preserve operator commands with explicit hub scope | delete in-epic |

## Планируемые этапы (до DECOMPOSE)

### Stage 1 — corpus contract and red inventory test

Define the exact discovery roots and exclusions in `loop/tests/test_stack_profile_instruction_inventory.py`. Replace fixed lists with deterministic globs for active `harness/cursor/rules/**`, selected `harness/claude/**`, both role-command skill copies, `harness/instructions/main.md`, templates, and hub operator docs. The classifier must distinguish positive action lines, negative policy lines, read-only prohibitions, explicit hub markers, and managed capability markers. Add a fixture that fails on `green (bin/pytest)` without scope and passes on separate hub/managed branches.

Red checks (all are hub tests of dev-hub):

```text
bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line
```

Expected before rewrites: FAIL with the existing BACK/INTEG workflow paths, stale `.agents` skill copy, and at least one unscoped template/entrypoint hit listed in the diagnostic.

### Stage 2 — BACK workflow and gate branch rewrite

Rewrite BACK workflow and lean-gate action sentences in the allowlisted BACK files. Each targeted/full/reproduce/coverage instruction has this shape:

```text
Hub (dev-hub self-test): `bin/pytest ...` from repository root under shared timeout.
Managed project: declare `capability_checks` (`test.targeted`/`test.full` or the named non-test capability) and consume typed execution evidence; do not substitute a raw runner.
```

Keep negative text that forbids fallback, but ensure no positive command appears before the hub condition. Update BACK QA wording so full suite remains hard for hub and full capability checks are hard for managed roots. Do not change `harness/hooks/tests_format.py`, capability registry, or evidence validators.

Stage verification:

```text
bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line -k 'back or runner or hub'
```

Expected: BACK-specific stale hits are gone; the test still accepts hub targeted/full fixtures.

### Stage 3 — INTEG, FRONT, shared and Claude branch rewrite

Update INTEG mode/core/lean surfaces so “pytest HTTP outcome” is explicitly a hub API-contract scenario; managed API checks use the declared capability and typed evidence. Keep browser scenario language and the FRONT parent-only rule; do not add `test.e2e`. Update FRONT core’s pytest sentence to hub-only plus managed reference. Update shared timeout/context economy text only where a direct runner is presented as generic; retain the shared timeout values and forbid bare commands.

Stage verification:

```text
bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line -k 'integ or front or shared or scenario'
```

Expected: no unqualified INTEG/FRONT/shared action lines; parent-only and no-`test.e2e` assertions remain green.

### Stage 4 — role skill, entrypoint and template parity

Bring `harness/skills/role-command/SKILL.md` to parity with the already branch-qualified Claude copy, preserving runtime-specific routing mechanics. Update `harness/instructions/main.md` with explicit root classification. Regenerate/inspect `AGENTS.md` and `CLAUDE.md` through the existing runtime materializer; add only the smallest semantic destination check if generated-header handling otherwise hides stale policy. Rewrite direct examples in plan/decompose/implement/QA/security/refactor/integration/finish templates and label `loop/WORKFLOW.md`/`loop/README.md` commands as dev-hub self-tests.

Stage verification:

```text
bin/pytest loop/tests/test_stack_profile_instruction_inventory.py loop/tests/test_runtime_sync_check.py -q --tb=line -k 'instruction or runtime_sync or parity'
```

Expected: both skill copies and runtime entrypoint markers match; no template or operator-doc direct command is ambiguous.

### Stage 5 — enforce purge and independent regression

Run the full corpus scan with all Kind I rows, compare source and symlinked runtime views, and run existing 076 hub/managed evidence tests. Capture exact `rg` output for old positive action forms and confirm only explicit hub/negative/archive/registry/test-code references remain. If a stale line remains, add it to the same stage’s `deletes`/rewrite set; do not mark the epic complete with a warning or leave a compatibility shim.

Required final commands:

```text
bin/pytest loop/tests/test_stack_profile_instruction_inventory.py harness/hooks/tests/test_epic_yaml_capability_evidence.py harness/hooks/tests/test_tests_format_managed_capabilities.py loop/tests/test_runtime_sync_check.py -q --tb=line
bin/pytest -q --tb=line
```

The second command is the BACK QA full suite for dev-hub itself. It is not a managed-project verification command.

## QA consumes (test plan)

### Scope under test

- Epic / surfaces: active workflow/rule/gate/skill/entrypoint/template corpus under `harness/**`, symlinked runtime views, and semantic inventory tests.
- Out of scope for QA: `loop/stack_profiles` executor/registry behavior, 077 receipt provenance, product application code, browser execution, package installation, archive/history prose, and arbitrary external managed commands.
- Test authority: parent runs all hub pytest commands; no subagent runs frontend tests.

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|---|---|---|---|---|---|
| TM-080-01 | P0 | Unqualified BACK workflow action | `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line -k back` | FAIL on stale line before rewrite; PASS with hub/managed branches and exact path diagnostics | FR-001–003; AC-1,2,4 |
| TM-080-02 | P0 | BACK lean gate reintroduces `.venv/bin/pytest` | same test `-k lean` plus `rg -n` over `_lean` | All positive action lines are branch-qualified; negative forbiddance remains accepted | FR-002,3; AC-1,4 |
| TM-080-03 | P0 | INTEG HTTP scenario and managed API distinction | `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line -k integ` | Hub HTTP outcome is explicit; managed branch points to capability/evidence; no browser executor vocabulary | FR-004; AC-2,8 |
| TM-080-04 | P0 | Full QA branch | `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line -k qa` | Hub full suite and managed full capability checks are both explicit; no universal `bin/pytest` | FR-003,4; AC-1,2 |
| TM-080-05 | P0 | Codex/Claude role-command parity | `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line -k role_command` | Both copies contain equivalent hub/managed semantics; stale `.agents` source fails | FR-006; AC-3 |
| TM-080-06 | P1 | Entrypoint source/destination parity | `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py loop/tests/test_runtime_sync_check.py -q --tb=line -k 'entrypoint or parity'` | Source and generated runtime views carry required markers; stale destination is reported | FR-007; AC-7 |
| TM-080-07 | P1 | Templates and operator docs | `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line -k template` | Direct examples are hub-only; managed examples use declarations/evidence; no ambiguous copy source | FR-008; AC-4 |
| TM-080-08 | P1 | 076 hub/managed contract regression | `bin/pytest harness/hooks/tests/test_epic_yaml_capability_evidence.py harness/hooks/tests/test_tests_format_managed_capabilities.py -q --tb=line` | Hub raw tests remain valid; managed tests-only proof remains rejected; no executor/registry drift | FR-010; AC-5,6 |
| TM-080-09 | P1 | FRONT boundary safety | `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py loop/tests/test_stack_profiles_schema.py -q --tb=line -k 'front or e2e'` | Parent-only frontend rule remains; capability enum has no `test.e2e` | FR-005,10; AC-8 |
| TM-080-10 | P1 | Full repository regression | `bin/pytest -q --tb=line` | Entire dev-hub suite passes after instruction rewrites | SC-008; AC-5 |

### Regression notes

- All commands in this matrix execute tests of dev-hub’s own source. They must run from repository root through `bin/pytest`; that does not authorize `bin/pytest` for a managed project.
- The semantic scanner must report line numbers and reasons, not only a boolean “managed” marker, so a future omitted workflow file produces an actionable failure.
- Archives and code/test imports may contain the word `pytest`; they are excluded only when the classifier can prove they are not executable instruction authority. A test that asserts the old managed contract is not an allowed exclusion.
- Symlinked `.cursor`/`.claude`/`.agents` views should be resolved for comparison but not edited independently.
- If runtime-sync destination bodies contain overlays, parity checks compare required policy markers and preserve overlay policy; they do not silently treat any generated header as semantic parity.

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| CLARIFY / Product probe | L3: one of done | done | Phase 0 taxonomy-clear rationale + six-question Product probe. |
| Eng review spine | L2+ | done | Source/runtime topology, semantic contract and eight-row failure matrix. |
| §0.11 counterparts (draft) | external refs in HOW | done | Role router → source rules → runtime views → inventory/evidence path mapped. |
| Delivery closure | P0/P1 runtime/instruction boundary | done | Two vertical-slice outcomes with production caller and fail-closed inventory test. |
| CREATIVE | if flagged | n/a | No UI, copy campaign or visual asset. |
| qa_consumes draft | L2+ | done | TM-080-01…TM-080-10, including full hub regression. |
| Plan review batch | L2+ | done | Product and Eng decisions recorded below; no unresolved Required item. |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|---|---|---|---|
| Product | Narrowed outcome to branch-qualified instruction behavior; preserved hub self-test and parent-only frontend exceptions. | Cosmetic wording cleanup in archive/history docs; no follow-up required because they are out of active authority scope. | Global deletion of `pytest` would break the explicit hub contract; ambiguity, not the token, is the defect. |
| Eng | Reused 076 capability/evidence SoT and shared timeout; selected corpus discovery over another hand-maintained allowlist; kept runtime projections non-authoritative. | Any broader redesign of generated-header overlays belongs to a separate runtime-sync epic if the minimal semantic check is insufficient. | A generated header must not turn stale body text into a false parity PASS; no direct managed fallback may remain. |

## До DECOMPOSE (черновик нарезки)

1. **s01 — corpus inventory contract and semantic regression test:** replace the seven-file presence test with deterministic active-surface discovery, action-context classification, stale-line diagnostics, hub exception fixtures, and FRONT/no-`test.e2e` assertions.
2. **s02 — BACK workflow branch rewrite:** update BACK mode workflows, core, and lean gates for targeted/reproduce/full/coverage wording; retain hub timeout and managed capability/evidence branches.
3. **s03 — INTEG/FRONT/shared branch rewrite:** update INTEG mode/core/lean scenario language, FRONT core, shared timeout/context economy, and parent-only boundary assertions.
4. **s04 — runtime skill/entrypoint/template parity:** update both role-command skill copies, main instruction source, generated destination checks, and all executable templates/operator docs that can teach a runner.
5. **s05 — legacy-fallback purge and regression:** full Kind I inventory, source/runtime parity scan, 076 evidence regression, and full hub suite; no stale positive action lines or over-broad deletions.

The outline follows `add → wire → enforce → purge`: s01 adds the executable corpus contract; s02–s04 wire every instruction family to it; s05 enforces zero stale action authority and purges the omitted surfaces. DECOMPOSE may merge s02/s03 only if all mode families remain separately checkpointed; it must not collapse them into a documentation-only mega-step.

## Appetite

| Поле | Значение |
|---|---|
| `timebox_days` | `2` |
| `cut_list` | `['archive/history prose cleanup', 'cosmetic wording normalization', 'new capability vocabulary', 'browser/E2E executor', 'runtime-sync overlay redesign', 'package installation and external managed command smoke']` |

## Independent Test

Create a temporary instruction corpus containing: (a) one stale `green (bin/pytest)` line, (b) one explicit hub-only line, (c) one managed `capability_checks` line, (d) one negative “no fallback to pytest” line, and (e) one stale Codex/Claude copy. Run the semantic inventory through the same discovery/classifier used for repository files. Assert that only (a) and (e) fail, with exact path/line/reason; (b), (c), and (d) pass. Then run the repository corpus and assert zero stale positive action lines across all active BACK/INTEG/FRONT/shared workflows, lean gates, skills, entrypoint source, templates, and operator docs. Finally run the existing 076 hub/managed evidence fixtures and full hub suite to prove the instruction fix neither restores generic managed authority nor removes the hub exception.

## Следующий режим

→ После PLAN FINISH workflow направляет `BACK DECOMPOSE` на `queue[0]` (сейчас это `T-HUB-077`); после выполнения стоящих перед ним эпиков очередь приведёт к `BACK DECOMPOSE T-HUB-080-workflow-capability-instruction-parity`. `T-HUB-076` остаётся hard prerequisite, а receipt integrity track не меняется.
