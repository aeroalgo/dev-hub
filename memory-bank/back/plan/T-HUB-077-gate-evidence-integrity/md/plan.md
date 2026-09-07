# T-HUB-077 — Неподделываемая целостность evidence для workflow-gate

**Дата:** 2026-09-07  
**Режим:** BACK PLAN · **Уровень:** L3 · **Статус:** draft  
**Clarify:** Phase 0 skipped — taxonomy clear; источник содержит конкретный incident, владельцев и проверяемый результат.  
**Prompt:** [md/prompt.md](prompt.md)
**Decompose index:** [md/decompose-index.md](decompose-index.md) · [yaml/decompose-index.yaml](../yaml/decompose-index.yaml)

## Контекст

Аудит `docs/audits/claude-code-last-20-sessions-audit-2026-09-07.md` зафиксировал ручные записи parent-агента в `runtime/**` и state `last_verify_*`: очистка `in_flight`, синтетический `PASS`, затем `finalize-step`. Текущие механизмы `harness/hooks/subagent-stop.py`, `harness/hooks/stop-gate.py`, `harness/hooks/epic/core.py` и `loop/mb_finish/*` частично проверяют evidence, но их тестовые helper API и доступный агенту shell позволяют обойти авторство результата.

### Product probe

| Probe | Ответ / решение |
|---|---|
| Реальная проблема | Владелец workflow не может отличить независимый verifier PASS от состояния, подложенного родительским агентом. |
| Узкий wedge | Сделать verifier receipt единственным допускаемым источником PASS для `mb-finish` и `finalize-step`. |
| Pre-mortem | Блокировка только prose не поможет: агент продолжит писать JSON через Python. Нужна enforcement boundary + негативные тесты. |
| Leverage | Использовать уже существующие identity/digest/epoch и не вводить второй статусный файл. |
| Appetite | 3 дня; не перепроектировать весь lifecycle и не менять продуктовые capability profiles. |

## Goal

Ни один parent/worker агент не может сам объявить verifier/reviewer PASS, очистить активный gate или завершить шаг по поддельному evidence; только runtime-путь, принявший завершённый проверочный subagent receipt с совпадающей identity, вправе записать результат.

## Delivery closure

| Outcome | Class | Production entrypoint | Enforcement | Independent test |
|---|---|---|---|---|
| Immutable verifier receipt | vertical_slice | `subagent-stop.py` → `mirror_gate_verdict` | direct runtime/state mutation → DENY | попытка finish с manual evidence возвращает non-zero |
| Fail-closed stale gate | vertical_slice | `stop-gate.py` / `mb-finish` | timeout/stale → typed infrastructure failure, не PASS | fixture stale receipt не даёт finalize |

## Functional requirements

- **FR-001:** PASS evidence имеет immutable provenance: `session_id`, `phase_epoch`, `projection/event digest`, role, step, verifier identity, receipt digest и время создания.
- **FR-002:** `mb-finish` и `finalize-step` принимают PASS только если provenance совпадает с текущим projection и receipt выпущен разрешённым verifier/reviewer runtime-path.
- **FR-003:** прямые write/edit/shell-write в runtime-gate, spawn-gate и `last_verify_*` запрещены агентскому tool boundary; нарушение observable и fail-closed.
- **FR-004:** `TaskStop`, отсутствующий receipt, stale `in_flight` и mismatch identity дают `GATE_INFRASTRUCTURE_FAILURE`/конкретный diagnostic, сохраняют forensic state и не запускают implicit retry.
- **FR-005:** repair path существует отдельно от worker workflow, требует human/operator authority и создаёт audit trail; он не может изготовить PASS.

## AC

1. Manual `last_verify_verdict='PASS'` или evidence с `authority=manual` не позволяют `mb-finish`/`finalize-step` завершить шаг.
2. Изменение любого signed/hashed поля receipt после создания обнаруживается до finish.
3. Parent может только ждать/читать typed status gate; не может очистить `in_flight` или редактировать runtime JSON.
4. Stale/TaskStop оставляет диагностируемую запись и переводит flow в stop/repair, а не в verifier retry loop.
5. Настоящий verifier PASS по действующему shard продолжает успешно проходить весь finish path.

### AC−

- Нет compatibility branch, где `authority=manual`, пустой receipt или state-only PASS эквивалентны verifier PASS.
- Нет диагностического auto-repair, который очищает `in_flight` либо зеркалит PASS.
- Нет разрешения общей записи в `runtime/**` «для тестов» вне test fixture/operator command.

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|---|---|---|
| Typed signed gate receipt, emitted runtime-only | schema-validated JSON with immutable digest | mutable state field как proof PASS |
| Fail-closed status enum | `passed|failed|stale|infrastructure_failure` | silent clear/retry/manual PASS |
| Operator-only repair command | explicit operator token/authority + audit event | repair from ordinary BACK IMPLEMENT shell |

## Техника / архитектура

```text
Verifier subagent completion
  -> subagent-stop validates identity and emits receipt
  -> atomic receipt store + event log
  -> mirror_gate_verdict records receipt reference/digest only
  -> stop-gate / mb-finish validates current identity + receipt
  -> finalize-step

Parent agent -> await_gate(status only) -> passed | failed | stale | infrastructure_failure
```

Состояние epic остаётся индексом последнего результата, но перестаёт быть источником полномочия. Source of truth — immutable receipt, связанный с текущей projection. `stop-gate` проверяет его до выхода; `mb-finish` повторяет проверку, чтобы direct CLI не обходил stop hook.

### Failure matrix

| Link | Failure | Detection | Response | Test |
|---|---|---|---|---|
| Parent → runtime JSON | write attempt | pretool policy | DENY + event | TM-077-01 |
| Receipt → epic mirror | digest mismatch | receipt validator | finish non-zero | TM-077-02 |
| Verifier ends abnormally | TaskStop/no receipt | lifecycle resolver | infrastructure_failure | TM-077-03 |
| Old receipt reused | epoch/session mismatch | identity compare | finish non-zero | TM-077-04 |
| Real verifier PASS | valid receipt | full validator | finish succeeds | TM-077-05 |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| Direct agent writes to `load_epic_state`/`save_epic_state` for `last_verify_*` | runtime-issued receipt reference | delete in-epic |
| permissive manual mirror path | verifier-only emitter | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| worker shell recipes manipulating `spawn-gate/*.json` | typed `await_gate` status command | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| clear stale marker and retry/force PASS | typed stale failure + operator repair | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| prompts suggesting inspection/edit of runtime gate state | wait/status + explicit failure handoff | delete in-epic |

## Stages

### Stage 1 — receipt contract and verifier-only emitter

- Add a versioned receipt schema and one constructor owned by `subagent-stop.py`/runtime integration.
- Make mirror APIs accept receipt reference, not arbitrary dict evidence, in production paths.
- Add Red tests for forged manual authority, digest mismatch and wrong role/step; Green only via valid verifier completion fixture.
- Define backward migration: old receipt-less state is rejected with a named diagnostic, never treated as PASS.

### Stage 2 — dual enforcement at stop and finish boundaries

- Validate receipt identity in both `stop-gate.py` and `mb_finish`/`finalize-step`; shared pure validator avoids diverging rules.
- Make status projection expose only read-only `passed|failed|stale|infrastructure_failure` to parent prompt building.
- Verify direct CLI cannot finalize with state that looks PASS but has no current receipt.

### Stage 3 — write-boundary and operator repair

- Extend pretool/tool policy so agent write attempts to runtime state and verifier fields are denied before shell execution where possible.
- Add immutable forensic event on stale/TaskStop; retain marker until operator repair resolves it.
- Implement a separately named operator repair flow with explicit authority, reason and audit event; it may restart a verifier but cannot set PASS.

### Stage 4 — purge and regression proof

- Remove obsolete manual-evidence helpers from production code and agent-facing instructions; retain fixture builders only under tests.
- Run all negative and positive finish/stop-gate regressions plus a targeted integration flow.
- Include a sunset inventory scan over symbols/prompt phrases and prove no live parent path can synthesize verifier proof.

## QA consumes

| ID | Priority | Scenario | Command | Expected | Maps |
|---|---|---|---|---|---|
| TM-077-01 | P0 | agent-style direct runtime write denied | targeted pretool/stop-gate pytest | PASS; denied diagnostic | FR-003 |
| TM-077-02 | P0 | forged/mutated receipt | finish integrity pytest | PASS; finish rejects | FR-001/2 |
| TM-077-03 | P0 | TaskStop/stale receipt | lifecycle pytest | PASS; typed fail, no retry | FR-004 |
| TM-077-04 | P0 | old epoch receipt replay | hook epoch pytest | PASS; reject | FR-002 |
| TM-077-05 | P0 | real verifier receipt | mb-finish implement pytest | PASS; finalize works | FR-005 |

## Review readiness

| Gate | Status | Evidence |
|---|---|---|
| Product probe | done | §Product probe |
| Eng spine | done | data flow + failure matrix |
| Delivery closure | done | vertical slices defined |
| qa_consumes | done | TM-077-01…05 |
| Plan review batch | done | no unresolved CRITICAL |

## Appetite and next mode

`timebox_days: 3`; cut first: cosmetic status UI and cross-runtime migration beyond Claude Code.  
→ **BACK DECOMPOSE T-HUB-077-gate-evidence-integrity**
