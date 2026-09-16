# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-098-managed-capability-sole-path  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-14  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3–L4  
**Granularity:** 5 sNN (band 5–8; classifier in s01; evidence provenance in s02; context_loop enforcement in s03; epic_yaml finish in s04; legacy purge & integration in s05).

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-098-managed-capability-sole-path/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 pure context classifier (hub vs managed) → s02 evidence provenance schema & authoritative read/write → s03 context_loop check-after managed enforcement → s04 epic_yaml finish capability gate → s05 legacy fallback purge and end-to-end integration tests.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |

**Per-step:** skills gate в каждом `sNN`. Session skills (`writing-plans`, `brainstorming`) **FORBIDDEN** в `impl:`.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR / US / SC → ≥1 шаг, иначе `out_of_scope` + `follow_up:` уже в `memory-bank/back/roadmap/queue.yaml`.  
> Колонка **Plan FR text** = дословно из `plan.md`. Covered row ⇒ measurable `verify` (не map-only).

| Req ID | Plan FR text (verbatim) | sNN | Notes / measurable verify |
| :--- | :--- | :--- | :--- |
| FR-001 | Add pure `classify_project_verification_context(project_root) -> hub\|managed` using strict manifest presence (T-HUB-075 loader); fail-closed on ambiguous/unreadable manifest for managed claim. | s01, s05 | `bin/pytest loop/tests/test_stack_profile_classifier.py -q` |
| FR-002 | When context is `managed`, finish validation (`epic_yaml.py` finish branches ~721–761 and step validator ~1813–1848) **requires** non-empty `capability_checks` on decompose shard for the finishing step; hub `tests:` alone MUST NOT satisfy verification; emit stable diagnostic `managed_verification_requires_capability_checks`. | s04, s05 | `bin/pytest harness/hooks/tests/test_epic_yaml_capability_checks.py -q` |
| FR-003 | Extend `_enforce_capability_checks_for_armed_step` / check_after path: if managed context and armed shard lacks `capability_checks`, return halt (not `None`); forbid treating absence as hub pass. | s03, s05 | `bin/pytest loop/tests/test_stack_profile_execution_integration.py -q` |
| FR-004 | Extend `CapabilityExecutionEvidence` (or companion schema field) with mandatory `provenance_source: Literal["executor"]` (or enum) set **only** by `write_capability_evidence` / executor integration in `loop/stack_profiles/execution.py` and context_loop writer; schema rejects agent-supplied values on read if not executor-issued. | s02, s05 | `bin/pytest loop/tests/test_stack_profile_evidence.py -q` |
| FR-005 | `read_capability_evidence` and finish gate MUST reject sidecars missing valid provenance even when fingerprint, status and exit_code match declaration; diagnostic `capability_evidence_non_authoritative`. | s02, s03, s04, s05 | `bin/pytest loop/tests/test_stack_profile_evidence.py -q` |
| FR-006 | Preserve hub-only branch: when context is `hub`, existing `tests:` validation unchanged; no mandatory `capability_checks`; no regression to T-HUB-098 I1 positive paths covered by QA TM-001…TM-006. | s04, s05 | `bin/pytest harness/hooks/tests/test_epic_yaml_capability_checks.py -q` |
| US-I2-001 | Как QA owner managed monorepo, я не могу завершить step только hub pytest, если в root лежит `dev-hub.project.yaml`, даже когда shard «забыл» capability_checks. | s04, s05 | `bin/pytest harness/hooks/tests/test_epic_yaml_capability_checks.py -q` |
| US-I2-002 | Как оператор loop, я вижу check-after HALT на managed armed step без declaration до любого hub test run. | s03, s05 | `bin/pytest loop/tests/test_stack_profile_execution_integration.py -q` |
| US-I2-003 | Как maintainer integrity boundary, я отвергаю capability sidecar, записанный агентом вручную, даже при valid fingerprint и status succeeded. | s02, s04, s05 | `bin/pytest loop/tests/test_stack_profile_evidence.py -q` |
| US-I2-004 | Как maintainer hub, я сохраняю hub self-test без manifest — существующие hub shards с `bin/pytest` остаются valid. | s04, s05 | `bin/pytest harness/hooks/tests/test_epic_yaml_capability_checks.py -q` |
| NFR-001 | Managed vs hub classification MUST be deterministic from filesystem manifest only; no environment flag bypass. | s01, s05 | `loop/tests/test_stack_profile_classifier.py` |
| NFR-002 | New diagnostics MUST be stable strings suitable for loop HALT and mb-finish error surfaces. | s02, s03, s04, s05 | `loop/tests/test_stack_profiles_integration.py` |
| NFR-003 | Provenance enforcement MUST NOT break operator CLI `python -m loop.stack_profiles execute` diagnostic flows (CLI is not finish proof unless wired through check-after). | s02, s05 | `loop/tests/test_stack_profile_execute_cli.py` |
| NFR-004 | Changes remain argv-only / no shell reconstruction; align with T-HUB-075 executor boundary. | s02, s05 | executor invocation contract |
| NFR-005 | I2 diff stays within gap surfaces; no expansion into agents corpus or TestFingerprintCache. | s01–s05 | scope lock |
| AC− 1 | No managed→hub fallback: presence of `dev-hub.project.yaml` MUST NOT allow hub `tests:` as sole verification. | s03, s04, s05 | `test_epic_yaml_capability_checks.py` |
| AC− 2 | No silent pass when `_enforce_capability_checks_for_armed_step` sees managed shard without checks. | s03, s05 | `test_stack_profile_execution_integration.py` |
| AC− 3 | No finish PASS on agent-written capability JSON regardless of fingerprint/status match. | s02, s04, s05 | `test_epic_yaml_capability_evidence.py` |
| AC− 4 | No new optional flag default-off that re-enables hub fallback for managed roots. | s01–s05 | hard architectural boundary |
| AC− 5 | No breaking hub self-test path when manifest absent. | s04, s05 | regression guard |
| AC− 6 | No scope creep into 077 write-deny implementation, 078 test cache, 080 agents inventory. | s01–s05 | out_of_scope |

## Stages coverage

| Stage | Focus | sNN |
|-------|-------|-----|
| Stage 1 | Classification: pure context classifier `classify_project_verification_context` | s01 |
| Stage 2 | Provenance & Authority: schema and sidecar read/write with executor provenance | s02 |
| Stage 3 | Runtime Enforcement: context_loop check-after halt on missing checks in managed context | s03 |
| Stage 4 | Gate Validation: epic_yaml finish validation requiring capability_checks and provenance | s04 |
| Stage 5 | Hardening & Purge: purge legacy fallback branches, verify TM-I2-076-01..05 test suite | s05 |

## Outcome map

| Outcome | Production entrypoints | Shards | Verification |
|---------|------------------------|--------|--------------|
| Pure context classification | `loop/stack_profiles/context.py` | s01 | `test_stack_profile_classifier.py` |
| Provenance-secured evidence | `loop/stack_profiles/schemas.py`, `loop/stack_profiles/evidence.py`, `loop/stack_profiles/execution.py` | s02 | `test_stack_profile_evidence.py` |
| Managed check-after halt | `loop/context_loop.py` | s03 | `test_stack_profile_execution_integration.py` |
| Managed finish requirement | `harness/hooks/epic_yaml.py` | s04 | `test_epic_yaml_capability_checks.py`, `test_epic_yaml_capability_evidence.py` |
| Legacy fallback elimination | `harness/hooks/epic_yaml.py`, `loop/context_loop.py`, `loop/stack_profiles/evidence.py` | s05 | `test_stack_profiles_integration.py` |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или OOS + follow-up в queue).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `else:` branch in finish validators running `validate_tests_entries` when `has_capability_checks` is false without checking managed root | A | managed classifier → require capability_checks or HALT | s04, s05 | no | `harness/hooks/epic_yaml.py` |
| `_enforce_capability_checks_for_armed_step` returning `None` when `capability_checks` absent in managed workspace | A | explicit managed halt diagnostic `managed_verification_requires_capability_checks` | s03, s05 | no | `loop/context_loop.py` |
| `read_capability_evidence` accepting any JSON matching fingerprint/status | A | provenance-validated authoritative read | s02, s05 | no | `loop/stack_profiles/evidence.py` |
| check-after green path on managed project without declaration execution | B | managed halt before continuation | s03, s05 | no | `loop/context_loop.py` |
| mb-finish accepting agent-written capability sidecar | B | provenance gate | s04, s05 | no | `harness/hooks/epic_yaml.py` |
| managed project + missing `capability_checks` → hub pytest proof | C | `managed_verification_requires_capability_checks` HALT | s03, s04, s05 | no | no fallback |
| fingerprint match without executor provenance → PASS | C | `capability_evidence_non_authoritative` | s02, s04, s05 | no | no fallback |
| finish-block prose implying hub pytest suffices inside managed repo | I | explicit managed diagnostic requirement | s04, s05 | no | full agents corpus owned by follow_up: T-HUB-080 |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-context-classifier.yaml](../yaml/steps/s01-context-classifier.yaml) | [s01…](../../implement/T-HUB-098-managed-capability-sole-path/s01-context-classifier.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-evidence-provenance-schema.yaml](../yaml/steps/s02-evidence-provenance-schema.yaml) | [s02…](../../implement/T-HUB-098-managed-capability-sole-path/s02-evidence-provenance-schema.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-context-loop-managed-enforcement.yaml](../yaml/steps/s03-context-loop-managed-enforcement.yaml) | [s03…](../../implement/T-HUB-098-managed-capability-sole-path/s03-context-loop-managed-enforcement.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-epic-yaml-managed-finish.yaml](../yaml/steps/s04-epic-yaml-managed-finish.yaml) | [s04…](../../implement/T-HUB-098-managed-capability-sole-path/s04-epic-yaml-managed-finish.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05…](../../implement/T-HUB-098-managed-capability-sole-path/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).
