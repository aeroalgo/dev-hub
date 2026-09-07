# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-077-gate-evidence-integrity  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — канон status  
**Дата:** 2026-09-07  
**Режим:** BACK DECOMPOSE

Эпик заменяет mutable evidence как authority на runtime-issued immutable verifier receipt.
Нарезка держит полный путь `red → receipt → stop/finish enforce → write boundary/repair → purge`;
каждый outcome проверяется production entrypoint, а не только helper/JSON-полем.

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | PASS evidence имеет immutable provenance: `session_id`, `phase_epoch`, `projection/event digest`, role, step, verifier identity, receipt digest и время создания. | s01, s02, s03, s05 | s01 red; s02 schema/emitter; s03 current validation; s05 removes alternate authority. |
| FR-002 | `mb-finish` и `finalize-step` принимают PASS только если provenance совпадает с текущим projection и receipt выпущен разрешённым verifier/reviewer runtime-path. | s01, s02, s03, s05 | Both stop and direct finish are covered; no state-only bypass. |
| FR-003 | прямые write/edit/shell-write в runtime-gate, spawn-gate и `last_verify_*` запрещены агентскому tool boundary; нарушение observable и fail-closed. | s04, s05 | s04 denies and logs; s05 purges recipes/helpers/instructions. |
| FR-004 | `TaskStop`, отсутствующий receipt, stale `in_flight` и mismatch identity дают `GATE_INFRASTRUCTURE_FAILURE`/конкретный diagnostic, сохраняют forensic state и не запускают implicit retry. | s01, s03, s04, s05 | Failure fixtures, dual enforcement, forensic event/operator repair, fallback purge. |
| FR-005 | repair path существует отдельно от worker workflow, требует human/operator authority и создаёт audit trail; он не может изготовить PASS. | s01, s04, s05 | Positive finish still requires a fresh verifier receipt. |
| AC+ #1 | Manual `last_verify_verdict='PASS'` или evidence с `authority=manual` не позволяют `mb-finish`/`finalize-step` завершить шаг. | s01, s02, s03, s05 | Direct production finish test, receipt-only mirror and final purge. |
| AC+ #2 | Изменение любого signed/hashed поля receipt после создания обнаруживается до finish. | s01, s02, s03 | Digest red test, schema validator and boundary checks. |
| AC+ #3 | Parent может только ждать/читать typed status gate; не может очистить `in_flight` или редактировать runtime JSON. | s03, s04, s05 | Read-only status projection plus tool deny and instruction purge. |
| AC+ #4 | Stale/TaskStop оставляет диагностируемую запись и переводит flow в stop/repair, а не в verifier retry loop. | s01, s03, s04, s05 | No-retry matrix, forensic record, operator-only repair and purge. |
| AC+ #5 | Настоящий verifier PASS по действующему shard продолжает успешно проходить весь finish path. | s01, s03, s04, s05 | Valid receipt positive path survives all enforcement and cleanup. |
| AC− #1 | Нет compatibility branch, где `authority=manual`, пустой receipt или state-only PASS эквивалентны verifier PASS. | s02, s03, s05 | Receiptless rejection, dual boundary, deletion scan. |
| AC− #2 | Нет диагностического auto-repair, который очищает `in_flight` либо зеркалит PASS. | s03, s04, s05 | Typed failure and operator-only restart; purge fallback. |
| AC− #3 | Нет разрешения общей записи в `runtime/**` «для тестов» вне test fixture/operator command. | s04, s05 | Pretool boundary and constrained fixture-only test support. |
| NFR: security/reproducibility before retry | Security and reproducibility take precedence over an automatic retry. | s03, s04, s05 | Typed terminal status, forensic retention and no silent fallback. |
| Independent test | Попытка finish с manual evidence возвращает non-zero; stale receipt не даёт finalize; real verifier receipt завершает finish. | s01, s03, s05 | Each condition has a named targeted pytest command. |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Red matrix: forged manual authority, digest mismatch, wrong role/step and valid verifier fixture | Plan Stage 1 | s01 |
| Versioned schema, runtime-only constructor and legacy receipt-less named rejection | Plan Stage 1 | s02 |
| Shared pure receipt validator at both stop and finish boundaries | Plan Stage 2 | s03 |
| Read-only `passed|failed|stale|infrastructure_failure` status projection | Plan Stage 2 | s03 |
| Tool write boundary for runtime/spawn gate and verifier fields | Plan Stage 3 | s04 |
| Forensic stale/TaskStop event and authority-gated operator repair | Plan Stage 3 | s04 |
| Remove manual helpers, recipes, soft-fail fallback and instructions | Plan Stage 4 | s05 |
| Negative/positive targeted integration regression and sunset inventory | Plan Stage 4; TM-077-01…05 | s05 |
| Add → wire → enforce → purge for sole PASS authority | behavior-first / spec-first canon | s02, s03, s04, s05 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Workflow completion is independently attributable rather than a mutable claim from the worker that benefits. | s01, s02, s03 |
| A forged, manually mirrored or replayed result cannot cross either stop or direct finish boundary. | s01, s02, s03, s05 |
| Interrupted verification is observable, forensic and fail-closed instead of silently retried. | s01, s03, s04, s05 |
| Human recovery is narrow and auditable but cannot manufacture successful verification. | s04, s05 |
| The valid independent verifier success path remains usable end-to-end after hardening. | s01, s03, s04, s05 |
| No agent-facing recipe or instruction reinstates the mutable gate authority. | s04, s05 |
| Out of scope: cosmetic status UI and cross-runtime migration beyond Claude Code. | —; Appetite cut |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Direct production writes to `load_epic_state`/`save_epic_state` for `last_verify_*` authority | A | Runtime-issued receipt reference/digest | s05 | no | s02 replaces mirror input; s05 proves no authority writer. |
| Permissive manual mirror path | A | Verifier-only runtime emitter | s05 | no | `authority=manual`, receipt-less and state-only PASS deleted. |
| Worker shell recipes manipulating `spawn-gate/*.json` | B | Typed `await_gate` status command | s05 | no | s04 denies tool writes before purge. |
| Clear stale marker and retry/force PASS | C | Typed stale failure plus operator repair | s05 | yes | Operator repair may re-arm only; cannot write PASS. |
| Prompts suggesting inspection/edit of runtime gate state | I | Wait/status and explicit failure handoff | s05 | no | Kind I scan includes agent-facing instructions. |

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-receipt-integrity-red-tests.yaml](../yaml/steps/s01-receipt-integrity-red-tests.yaml) — red manual/forged/stale/real matrix | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-immutable-verifier-receipt-contract.yaml](../yaml/steps/s02-immutable-verifier-receipt-contract.yaml) — schema and runtime-only emitter | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-stop-finish-receipt-enforcement.yaml](../yaml/steps/s03-stop-finish-receipt-enforcement.yaml) — stop/finish dual enforcement | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-write-boundary-operator-repair.yaml](../yaml/steps/s04-write-boundary-operator-repair.yaml) — deny mutation and audited repair | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) — A+B+C+I purge and regression proof | no | yes | BACK IMPLEMENT | pending |

Следующая фаза после DECOMPOSE — **BACK ANALYZE**. Переход к IMPLEMENT до ANALYZE с `critical_count=0` запрещён.
