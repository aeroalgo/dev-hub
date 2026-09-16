# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-099-execution-evidence-write-deny  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-14  
**Режим:** BACK DECOMPOSE  
**Уровень:** L2  
**Granularity:** 5 sNN (band 5–8; red fixtures in s01; predicate in s02; pretool wiring in s03; finish non-authoritative enforcement in s04; sunset & integration in s05).

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-099-execution-evidence-write-deny/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 red tests → s02 execution evidence write deny predicate → s03 pretool WritePolicyAdapter wiring → s04 finish read non-authoritative enforcement → s05 legacy fallback purge & integration.

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
| FR-001 | Extend `recorded_artifact_write_deny_reason` (or dedicated sibling `execution_evidence_write_deny_reason`) to match `memory-bank/{back,front,integration}/execution/{epic_id}/{step_id}/capability-*.json` using path-safe glob/regex; return stable deny string. | s01, s02, s05 | `bin/pytest harness/hooks/tests/test_agent_pretool_gate_write_boundary.py -k test_execution_evidence_write_deny_reason` |
| FR-002 | Wire new deny into `WritePolicyAdapter.evaluate` in `pretool_policy.py` before other allows; Write and Edit aliases covered. | s01, s03, s05 | `bin/pytest harness/hooks/tests/test_agent_pretool_gate_write_boundary.py -k test_write_execution_evidence` |
| FR-003 | Deny MUST apply to agent tool boundary for all roles; executor/check-after write path MUST remain allowed via allowlist (hook identity, subprocess writer, or temp-file atomic replace from trusted caller — exact mechanism in DECOMPOSE, but outcome is sole mutator). | s01, s02, s03, s04, s05 | `bin/pytest harness/hooks/tests/test_epic_yaml_capability_evidence.py -k test_write_capability_evidence` |
| FR-004 | Integrate finish/read non-authoritative rejection for capability sidecars missing valid executor provenance (delegate to `read_capability_evidence` from 076; 077 adds hook-level tests proving agent cannot establish authority via Write). | s01, s04, s05 | `bin/pytest harness/hooks/tests/test_epic_yaml_capability_evidence.py -k test_forged_capability_evidence` |
| FR-005 | Preserve I1 verifier receipt enforcement (FR-001…I1 FR-005); no regression on TM-077-01…05; no new manual PASS paths. | s01, s04, s05 | `bin/pytest harness/hooks/tests/test_stop_gate_receipt_integrity.py` |
| US-I2-001 | Как security boundary, я блокирую agent Write/Edit capability sidecar до записи на диск. | s01, s02, s03, s05 | `bin/pytest harness/hooks/tests/test_agent_pretool_gate_write_boundary.py` |
| US-I2-002 | Как finish gate, я не принимаю capability JSON, появившийся минуя executor, даже если deny обошли через shell heredoc. | s01, s04, s05 | `bin/pytest harness/hooks/tests/test_epic_yaml_capability_evidence.py` |
| US-I2-003 | Как operator, я сохраняю I1 verifier receipt integrity — новый deny не ломает runtime gate JSON paths. | s01, s04, s05 | `bin/pytest harness/hooks/tests/test_stop_gate_receipt_integrity.py` |
| US-I2-001 (AS) | Write deny on execution evidence: Write/Edit to `memory-bank/<role>/execution/<epic_id>/<step_id>/capability-<fingerprint>.json` returns DENY before tool execution. | s01, s03, s05 | `test_agent_pretool_gate_write_boundary.py` |
| US-I2-002 (AS) | deny covers role variants: paths under `memory-bank/back/execution/`, `memory-bank/front/execution/`, `memory-bank/integration/execution/` denied uniformly. | s01, s02, s03, s05 | `test_agent_pretool_gate_write_boundary.py` |
| US-I2-003 (AS) | finish read rejects non-authoritative capability evidence lacking executor `provenance_source`. | s01, s04, s05 | `test_epic_yaml_capability_evidence.py` |
| US-I2-004 (AS) | I1 gate receipts unaffected: existing runtime gate JSON receipt integrity checks pass. | s01, s04, s05 | `test_stop_gate_receipt_integrity.py` |
| NFR-001 | Deny reason strings MUST be machine-stable for pretool telemetry and agent additionalContext. | s02, s03, s05 | pretool telemetry verification |
| NFR-002 | Path matching MUST use resolved relative path under project root; no directory traversal bypass. | s02, s05 | path resolution traversal unit tests |
| NFR-003 | Performance: deny check is O(1) regex on path, no full events.jsonl scan for execution paths. | s02, s05 | benchmark/unit assertion |
| NFR-004 | Provider parity: Claude pretool and Codex bridge route through same `WritePolicyAdapter`. | s03, s05 | adapter routing verification |
| AC− 1 | No agent Write/Edit success on capability execution sidecar paths in pretool fixtures. | s01, s03, s05 | negative pretool assertions |
| AC− 2 | No finish PASS solely because a forged sidecar exists with succeeded status. | s01, s04, s05 | negative finish assertions |
| AC− 3 | No regression of I1 verifier receipt deny paths (runtime gate JSON still governed by I1 rules). | s01, s03, s05 | regression guard |
| AC− 4 | No implementation of managed->hub fallback fix (follow_up: T-HUB-076). | s01–s05 | out_of_scope (follow_up: T-HUB-076) |
| AC− 5 | No scope into TestFingerprintCache or clear_open_on_start (follow_up: T-HUB-078, follow_up: T-HUB-079). | s01–s05 | out_of_scope (follow_up: T-HUB-078, follow_up: T-HUB-079) |
| TM-I2-077-01 | Agent Write capability sidecar denied (P0). | s01, s02, s03, s05 | `test_agent_pretool_gate_write_boundary.py` |
| TM-I2-077-02 | Agent Edit existing capability sidecar denied (P0). | s01, s03, s05 | `test_agent_pretool_gate_write_boundary.py` |
| TM-I2-077-03 | Forged sidecar without provenance -> finish fail (P0). | s01, s04, s05 | `test_epic_yaml_capability_evidence.py` |
| TM-I2-077-04 | I1 verifier receipt positive path regression (P1). | s01, s04, s05 | `test_stop_gate_receipt_integrity.py` |
| TM-I2-077-05 | Executor/check-after write path still permitted (P1). | s01, s03, s04, s05 | `test_epic_yaml_capability_evidence.py` |

## Stages coverage

| Stage | Focus | sNN |
|-------|-------|-----|
| Stage 1 | TDD Red: failing fixtures for execution evidence write deny and forged finish reject | s01 |
| Stage 2 | Predicate: path-safe execution_evidence_write_deny_reason in _lib.py | s02 |
| Stage 3 | Pretool Boundary: wire deny into WritePolicyAdapter and pretool hook dispatch | s03 |
| Stage 4 | Finish Enforcement: non-authoritative read rejection during finish validation | s04 |
| Stage 5 | Sunset & Integration: inventory audit, fallback purge, full TM-I2-077-01..05 matrix | s05 |

## Outcome map

| Outcome | Production entrypoints | Shards | Verification |
|---------|------------------------|--------|--------------|
| Pretool write deny predicate | `harness/hooks/_lib.py` | s02 | `test_agent_pretool_gate_write_boundary.py` |
| Pretool policy enforcement | `harness/hooks/pretool_policy.py`, `harness/hooks/agent-pretool.py` | s03 | `test_agent_pretool_gate_write_boundary.py` |
| Finish non-authoritative reject | `harness/hooks/epic_yaml.py`, `loop/stack_profiles/evidence.py` | s04 | `test_epic_yaml_capability_evidence.py` |
| Sunset & regression closure | `harness/hooks/_lib.py`, `harness/hooks/pretool_policy.py`, `harness/hooks/epic_yaml.py` | s05 | `test_agent_pretool_gate_write_boundary.py`, `test_epic_yaml_capability_evidence.py`, `test_stop_gate_receipt_integrity.py` |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или OOS + follow-up в queue).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Absence of write deny on `memory-bank/*/execution/**/capability-*.json` | A | pretool DENY via `execution_evidence_write_deny_reason` | s03, s05 | no | `harness/hooks/pretool_policy.py` |
| Finish accepting any readable JSON at evidence path | A | provenance-aware read and authoritative validation | s04, s05 | no | `harness/hooks/epic_yaml.py`, `loop/stack_profiles/evidence.py` |
| Agent Write as capability proof transport | B | executor-only check-after write + agent tool deny | s03, s05 | no | `harness/hooks/pretool_policy.py` |
| "File exists => evidence OK" for capability sidecars | C | `capability_evidence_non_authoritative` | s04, s05 | no | no fallback |
| Prompts suggesting manual creation of capability JSON | I | deny + wait for check-after (note-only) | s05 | no | full agents corpus owned by follow_up: T-HUB-080 |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-red-tests-execution-evidence-write-deny.yaml](../yaml/steps/s01-red-tests-execution-evidence-write-deny.yaml) | [s01…](../../implement/T-HUB-099-execution-evidence-write-deny/s01-red-tests-execution-evidence-write-deny.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-execution-evidence-write-deny-predicate.yaml](../yaml/steps/s02-execution-evidence-write-deny-predicate.yaml) | [s02…](../../implement/T-HUB-099-execution-evidence-write-deny/s02-execution-evidence-write-deny-predicate.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-pretool-write-policy-adapter-wiring.yaml](../yaml/steps/s03-pretool-write-policy-adapter-wiring.yaml) | [s03…](../../implement/T-HUB-099-execution-evidence-write-deny/s03-pretool-write-policy-adapter-wiring.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-finish-read-non-authoritative-enforcement.yaml](../yaml/steps/s04-finish-read-non-authoritative-enforcement.yaml) | [s04…](../../implement/T-HUB-099-execution-evidence-write-deny/s04-finish-read-non-authoritative-enforcement.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05…](../../implement/T-HUB-099-execution-evidence-write-deny/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).
