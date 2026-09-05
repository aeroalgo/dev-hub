# 05. Аудит repair agents, verdict flow и stop gates

## 1. Intended flow

```text
parent spawns verify
  → SubagentStart injects compact contract
  → verify reads bounded ALLOW READ
  → verify emits gate JSON
  → SubagentStop validates/retries
  → PASS: mirror evidence + parent may mb-finish
  → FAIL: parent spawns gate-repair
  → gate-repair writes only ALLOW WRITE + runs VERIFY
  → repair JSON
  → SubagentStop stores repair status
  → parent retries verify
  → PASS → finalize-step
```

Это разумная схема. Основные дыры находятся на boundaries между шагами.

## 2. SubagentStart

`harness/hooks/subagent-start.py`:

- нормализует `agent_type/subagent_type/type`;
- inject-ит `CONTRACTS[agent_type]` и global `HARD_RULE`;
- для verify/reviewer/gate-repair contract inject-ится даже вне active workflow;
- explorer/sunset требуют active workflow state.

### Findings

### P1 — injected contract и native prompt могут расходиться

Subagent получает одновременно полный markdown prompt и короткий `_lib.CONTRACTS`. Если тексты различаются, модель видит две версии “HARD”. Hook не проверяет, что injected contract соответствует hash текущего prompt.

Усиление: contract ID + version + source hash, например:

```text
contract=verify-implement/v2 source_sha256=...
```

При mismatch не запускать agent и выдавать `agent_contract_drift`.

### P1 — `_ALWAYS_INJECT` не совпадает с phase registry

Set содержит software verify agents и gate-repair, но не `verify-script`, `verify-edit`, `verify-publish` и не sunset. Это прямой symptom отсутствия единого contract registry.

## 3. SubagentStop gate validation

Сильные стороны:

- gate schema errors переводятся в retry;
- после двух gate retries — `NEED_HUMAN: schema_retry_exhausted:B-GATE`;
- repair имеет отдельный лимит retry;
- verdict записывается в state и sidecar;
- после PASS state очищает in-flight и schema retry counters;
- `verify-qa` может выдать BLOCKED и направить QA→BUGFIX.

### P0/P1 holes

1. Payload `data.verdict` может обойти обязательный JSON fence — см. [04-schemas-validation.md](./04-schemas-validation.md).
2. Sunset branch отсутствует.
3. `parse_gate_verdict_message()` поддерживает legacy unversioned object и пишет sidecar до строгого end-to-end decision.
4. `extract_verdict()` допускает schema=None.
5. Exceptions при `coerce_verify_verdict()` и mirror verdict печатаются, но не обязательно блокируют transition.
6. Hook сначала изменяет state для repair (`clear_in_flight`, `repair_in_flight=False`), а затем при невалидном JSON возвращает retry. Это может быть нормально для retry, но восстановление parent context/in-flight должно быть явно idempotent.

## 4. P1 — repair result не связан с исходным FAIL

`RepairResultRecord` содержит `agent_id`, `status`, `fixed_blockers`, `remaining_blockers`, `recorded_at`, но не содержит:

- `parent_gate_id` или `verify_evidence_sha256`;
- `epic_id`, `step_id`, `session_id`;
- `allowed_write_hash`/список изменённых файлов;
- exact parent blocker ids;
- verification command result/hash.

Поэтому `status=done` — структурно валидный, но система не доказывает, что исправлены именно текущие blockers. Parent может сформировать новый verify prompt с другим scope.

Рекомендуемый record:

```json
{
  "schema": "loop-repair-result/v2",
  "agent_id": "gate-repair",
  "parent_gate": {"agent_id":"verify-implement", "evidence_sha256":"..."},
  "context": {"epic_id":"...", "step_id":"s01", "session_id":"..."},
  "status": "done",
  "fixed_blockers": ["B-001"],
  "remaining_blockers": [],
  "changed_files": ["..."],
  "verify": {"command":"bin/pytest ...", "exit_code":0}
}
```

## 5. P1 — semantic validator нужен после schema validator

Сейчас `validate_boundary()` отвечает на вопрос “это JSON правильной формы?”. Для repair/verdict нужно второй решение:

```text
SchemaValidation
  → ContractValidation (agent/phase/required sections)
  → OwnershipValidation (epic/step/session/evidence)
  → TransitionValidation (PASS/FAIL/BLOCKED allowed next state)
```

Например:

- `verify-implement PASS` разрешает `mb-finish implement` только если current phase IMPLEMENT и same step;
- `verify-qa BLOCKED` разрешает только BUGFIX, но не DONE;
- `gate-repair done` запрещает finish и разрешает только verify retry;
- `verify-decompose PASS` разрешает next ANALYZE;
- video `verify-edit PASS` требует external render gate pass.

## 6. Stop gate: что уже хорошо

`stop-gate.py` учитывает:

- active workflow/epic;
- registry agent availability and model validity;
- stale gate identity;
- schema retry exhaustion;
- external gates from phase config;
- DECOMPOSE verify-decompose;
- verify/reviewer required states;
- QA handoff;
- finish integrity and stale `load_now`.

Это правильное место для final fail-closed decision.

## 7. Stop gate: что усилить

- не считать `agent_disabled` равнозначным безопасному bypass без explicit policy event;
- для each phase получать required agents из phase registry, а не hardcoded `verify/reviewer` assumptions;
- reject missing/invalid pack routes before attempting finish;
- принимать только current typed evidence record, а не только `state["verify_done"]`;
- проверять monotonic transition: `PASS` не должен быть перезаписан старым `FAIL` или чужим session;
- использовать event sequence/epoch, чтобы поздний SubagentStop не мог очистить новый in-flight;
- убрать broad `except Exception: log and continue` на critical mirror/identity operations.

## 8. Codex collaboration bridge

`loop/codex_collab_verdict.py` имеет отдельный `_CollabGateVerdictFence` с `extra="ignore"`, optional schema и только gate verdict support. Затем он вызывает `subagent-stop.py`, что частично возвращает canonical validation.

Риски:

- два parser implementations с разной strictness;
- Codex bridge умеет только gate verdict, не repair/sunset;
- agent type выводится из prompt `@...` и может быть неоднозначен;
- tool/thread identity не является частью schema record;
- downstream validation зависит от того, что в message сохранился оригинальный JSON fence.

Исправление: bridge должен создавать canonical typed envelope и передавать `source_runtime`, `thread_id`, `tool_use_id`, `message_sha256`; не парсить gate schema собственной моделью.

## 9. Retry policy

Текущие лимиты полезны, но должны быть единообразны и наблюдаемы:

| Boundary | Сейчас | Проблема |
|---|---:|---|
| gate schema | до 2 retry | bypass payload verdict |
| repair schema | 1 retry | нет parent identity |
| no verdict | отдельные counters | разные сообщения `BLOCKED`/`NEED_HUMAN` |
| semantic failure | часто остаётся на parent | нет unified taxonomy |

Добавить `retry_policy/v1` в registry: `max_attempts`, `retry_on`, `escalate_to`, `preserve_in_flight`, `idempotency_key`.

## 10. Что убрать

- legacy parser в общем пути после migration window;
- отдельный Codex schema model;
- catch-and-continue для обязательного mirror/identity;
- hardcoded agent sets в `subagent-start`, `verify_hint`, `parity`, если phase/manifest уже являются SoT;
- generic `@verify` там, где конкретный agent обязателен.

## 11. Acceptance criteria

- invalid/no-fence verdict не проходит ни через один runtime;
- каждый repair result можно связать с конкретным parent FAIL;
- late/duplicate SubagentStop idempotent и не меняет новый gate state;
- all phase verify agents проходят одинаковую typed pipeline;
- semantic/ownership failures не маскируются schema retry;
- stop gate принимает решение по одному canonical evidence record.
