# [T-HUB-085 | hook-event-dispatcher-consolidation] PLAN

**Дата:** 2026-09-07  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** draft  
**Clarify:** Phase 0 skipped — taxonomy clear: пользовательский outcome и границы определены в запросе; as-built corpus зарегистрированных hooks прочитан.  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `hook-runtime-optimization-20260907`  
**Deps:** hard T-HUB-063 (SubagentStop boundary), T-HUB-065 (unique runtime hook registration); hard T-HUB-077 (trusted evidence) and T-HUB-079 (invocation lifecycle) before cutover; soft T-HUB-066 (ownership schema) and T-HUB-080 (capability parity).  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  

## Контекст и цель

Текущий harness регистрирует несколько отдельных Python-процессов на каждый lifecycle event. Часть проверок логически связана, но разнесена по самостоятельным entrypoint-файлам: pre-tool policy находится в `agent-pretool.py`, `bash-pretool.py`, `write-pretool.py` и `finish-boundary-pretool.py`; post-tool обработка — в `agent-posttool.py` и `bash-output-cap.py`; gate state и verdict повторно извлекаются в нескольких местах.

Цель эпика — сократить процессный и кодовый overhead через event-specific dispatchers и единые pure policy services, сохранив независимые границы доверия. Это не означает объединение всех lifecycle events в один универсальный hook и не означает удаление внешней проверки `SubagentStop`.

### Product probe

| Реальная проблема | Wedge | Pre-mortem | Appetite |
|---|---|---|---|
| Избыточные запуск/парсинг и расхождение одинаковых policy checks | dispatcher на `PreToolUse` и `PostToolUse` плюс общий gate/evidence service | смешение response-контрактов заблокирует разрешённый tool или позволит обход gate | 4 дня |

### Reframe

Нужно не «сделать один hook», а уменьшить количество независимых реализаций и subprocess invocations внутри каждого события, оставив отдельными точки до инструмента, после инструмента, завершения subagent и завершения parent turn.

### Anti-scope

- Не объединять `SubagentStart`, `SubagentStop` и `Stop` в один lifecycle handler.
- Не удалять независимую runtime-проверку результата агента.
- Не менять модели verdict, schema IDs, ownership semantics и phase transition policy.
- Не менять Codex/Claude parity matrix; адаптеры потребляют те же dispatch contracts.
- Не делать LLM-summary частью authorization или gate decision.

## WHAT

### User stories

| ID | Story | Priority | Independent test |
|---|---|---:|---|
| US-001 | Как runtime, я хочу один pre-tool entrypoint на событие, чтобы policy checks выполнялись детерминированно и без конфликтующих ответов. | P0 | fixture для Agent/Bash/Write/Read сравнивает старые и новые decisions |
| US-002 | Как runtime, я хочу один post-tool entrypoint на событие, чтобы agent state и Bash output shaping не дублировали dispatcher plumbing. | P0 | Agent и Bash fixtures сохраняют прежние side effects |
| US-003 | Как gate, я хочу общий pure validator для schema/identity/evidence, но отдельный `SubagentStop` boundary. | P0 | forged/mismatch payload отвергается на stop boundary |
| US-004 | Как оператор, я хочу видеть, какой dispatch branch сработал и почему был deny/retry. | P1 | structured diagnostic содержит event, branch и code |
| US-005 | Как CI, я хочу запрещать возвращение duplicate active hook commands и мёртвых dispatcher references. | P1 | registration/reference scan fails closed |

### Functional requirements

- **FR-001:** Ввести event-specific dispatch layer с отдельными входами для `pretool`, `posttool`, `subagent_start`, `subagent_stop` и `stop`; dispatcher не смешивает события и не скрывает отказ.
- **FR-002:** `PreToolUse` сохраняет порядок policy: project boundary → finish boundary → tool-specific policy; первый deny является итогом, allow возвращает все нужные `updatedInput` mutations.
- **FR-003:** `PreToolUse` dispatcher маршрутизирует Agent/Task, Bash, Write/Edit/NotebookEdit и generic tools по `tool_name`, сохраняя текущие matcher semantics.
- **FR-004:** `PostToolUse` dispatcher маршрутизирует Agent/Task и Bash; agent state/evidence и output-cap не вызывают друг друга и сохраняют прежние payload response fields.
- **FR-005:** Общие pure services для `state identity`, `verdict extraction`, `boundary validation`, `evidence recording` и `diagnostic codes` имеют один контракт и используются hooks/CLI без копирования алгоритма.
- **FR-006:** `SubagentStart` остаётся отдельной точкой contract injection и drift deny; `SubagentStop` остаётся отдельной точкой фактического transcript validation.
- **FR-007:** `Stop` остаётся отдельным final gate и использует общий read-only status/evidence service, но не доверяет состоянию, созданному только parent agent.
- **FR-008:** Manifest/materializer и committed settings регистрируют ровно один canonical command на `(event, matcher, realpath)`; dispatcher migration не создаёт dual path.
- **FR-009:** Self-check агента `validate-boundary` и внешний `SubagentStop` validation сохраняются как два разных trust boundary; разрешается общий library implementation, но не удаление внешней проверки.
- **FR-010:** Каждый dispatch branch имеет deterministic diagnostic при deny/retry/error; исключение не превращается в silent allow.
- **FR-011:** Старые entrypoints либо становятся тонкими compatibility wrappers с одним canonical implementation, либо удаляются внутри эпика; вечный dual implementation запрещён.
- **FR-012:** Тесты проверяют parity positive/negative side effects, subprocess registration count, ordering, idempotency и fail-closed behavior.

### Non-functional requirements

- **NFR-001:** Снижение числа registered command entries минимум с текущих 11 до целевого event-specific набора без снижения числа lifecycle boundaries.
- **NFR-002:** Dispatcher branch должен быть синхронным и bounded; не добавлять сетевой/LLM вызов в authorization path.
- **NFR-003:** Все deny/retry decisions остаются fail-closed; неизвестный event/tool/branch не получает implicit allow.
- **NFR-004:** State mutation выполняется только один раз за hook event и остаётся idempotent по `(session_id, tool_use_id, agent_type, verdict)`.
- **NFR-005:** Полный вывод Bash по-прежнему сохраняется до сокращения, если включён output cap; dispatcher не теряет dump path.
- **NFR-006:** Новые публичные helper API покрываются typed input/output и не принимают произвольные state dict как proof PASS.

### Acceptance criteria

1. На `PreToolUse` зарегистрирован один canonical dispatcher; Agent/Bash/Write/generic fixtures получают те же allow/deny и updated input semantics.
2. На `PostToolUse` зарегистрирован один canonical dispatcher; Agent verdict/evidence и Bash output cap сохраняют текущие side effects.
3. `SubagentStart`, `SubagentStop` и `Stop` остаются раздельными entries и проходят отдельные event tests.
4. Внешний `SubagentStop` отвергает malformed fence, schema mismatch, ownership mismatch и stale identity даже если агентский self-check был успешен.
5. `Stop` не принимает state-only/manual PASS и не разрешает finish без обязательного gate.
6. Duplicate realpath scan даёт ноль active duplicates; old entrypoints не вызываются из settings/manifest.
7. Все старые registered hook behavior tests зелёные либо заменены parity tests с тем же acceptance.
8. Diagnostics позволяют отличить `deny`, `retry`, `recorded`, `output_capped`, `stale` и `infrastructure_failure`.

### Acceptance criteria — negative

- Нельзя получить allow, если любой обязательный pretool policy вернул deny.
- Нельзя получить PASS только потому, что parent записал verdict/state вручную.
- Нельзя заменить фактический transcript SubagentStop результатом, который агент проверил сам.
- Нельзя запустить одновременно две managed gate branches для одной identity.
- Нельзя зарегистрировать одновременно wrapper и canonical dispatcher на одном event/matcher.
- Нельзя потерять полный Bash dump из-за dispatcher exception.

## Technology axiom

| Выбор | Machine input | Запрещено после эпика |
|---|---|---|
| Event-specific dispatch | event payload + normalized tool/event type | один универсальный hook с неявным lifecycle branching |
| Pure policy service | typed decision/result | копирование deny logic в каждом entrypoint |
| Runtime gate | фактический SubagentStop/Stop payload | доверие self-check агента как final proof |
| Canonical registration | manifest → unique realpath settings | ручной dual registration |
| Evidence | receipt/status reference и current identity | произвольный mutable dict как PASS |

## As-built route map

```text
SessionStart        -> session-start.py
UserPromptSubmit    -> user-prompt.py
PreToolUse Agent    -> agent-pretool.py
PreToolUse Bash     -> bash-pretool.py
PreToolUse Write    -> write-pretool.py
PreToolUse .*       -> finish-boundary-pretool.py
PostToolUse Agent   -> agent-posttool.py
PostToolUse Bash    -> bash-output-cap.py
SubagentStart       -> subagent-start.py
SubagentStop        -> subagent-stop.py
Stop                -> stop-gate.py
```

Target route:

```text
PreToolUse .*  -> pretool-dispatch.py
                  ├─ project/finish boundary
                  ├─ Agent policy
                  ├─ Bash policy
                  └─ Write policy

PostToolUse .* -> posttool-dispatch.py
                  ├─ Agent result/evidence
                  └─ Bash output cap

SubagentStart -> subagent-start.py -> shared contract service
SubagentStop  -> subagent-stop.py  -> shared boundary/evidence service
Stop          -> stop-gate.py      -> shared lifecycle/status service
```

`SessionStart` и `UserPromptSubmit` остаются самостоятельными, потому что формируют разные контексты и имеют разные state transition semantics. `SubagentStart`, `SubagentStop` и `Stop` остаются самостоятельными, потому что их payload и trust boundary не совпадают.

## HOW / proposed file boundaries

### New shared modules

- `harness/hooks/hook_dispatch.py` — normalized event/tool context, ordered branch execution, decision merge, diagnostic envelope; без state-specific policy.
- `harness/hooks/pretool_policy.py` — pure project boundary, finish boundary, agent spawn, bash and write policy adapters.
- `harness/hooks/posttool_policy.py` — pure Agent result and Bash output-cap adapters.
- `harness/hooks/gate_runtime.py` — shared typed helpers для boundary validation, identity matching, retry classification и evidence recording; не владеет event registration.
- `harness/hooks/tests/test_hook_dispatch.py` — table-driven routing/order/merge tests.
- `harness/hooks/tests/test_hook_registration_consolidation.py` — manifest/settings realpath and active reference tests.

### Existing modules to modify

- `harness/hooks/agent-pretool.py` — thin canonical adapter or removal after dispatcher cutover.
- `harness/hooks/bash-pretool.py` — thin canonical adapter or removal after dispatcher cutover.
- `harness/hooks/write-pretool.py` — thin canonical adapter or removal after dispatcher cutover.
- `harness/hooks/finish-boundary-pretool.py` — move pure policy into shared service; preserve public test helper during migration only.
- `harness/hooks/agent-posttool.py` — move result recording to shared service; preserve response compatibility.
- `harness/hooks/bash-output-cap.py` — move routing/entrypoint only; preserve dump and shaping implementation.
- `harness/hooks/subagent-start.py` — consume shared contract service; no event merge.
- `harness/hooks/subagent-stop.py` — consume shared gate/evidence service; no removal of independent validation.
- `harness/hooks/stop-gate.py` — consume shared lifecycle/status service; retain final gate ownership.
- `harness/manifest.yaml` — canonical hook commands and generated materialization rules.
- `.claude/settings.json` — generated result only; no hand-maintained duplicate entries.

### Out of scope files

- `harness/hooks/epic_resolve.py` subcommand semantics, кроме optional internal import of shared validator.
- `loop/schemas/**` schema definitions, кроме compatibility imports required by shared gate service.
- `loop/mb_finish/**` finish policy, кроме tests proving unchanged behavior.
- `.cursor/rules/**` workflow policy, кроме explicit documentation of canonical hook command if a dangling reference is found.

## Data and control flow

```text
Claude event payload
  -> read_stdin / normalize context
  -> dispatcher selects event branch
  -> ordered pure policy checks
  -> one decision envelope
  -> optional state/evidence side effect
  -> Claude hook response
```

### Decision merge contract

- `DENY` is terminal and includes the first stable diagnostic plus all non-sensitive contributing codes.
- `ALLOW` may include exactly one normalized `updatedInput` or `updatedToolOutput` appropriate to the event.
- `RETRY` is emitted only by SubagentStop schema/semantic handling; pre/post dispatchers never synthesize a verifier retry.
- `ERROR` is fail-closed for gate events and observable for non-gate output shaping.
- Unknown tool/event is not silently treated as a managed gate; it follows the existing generic boundary policy and is covered by a fixture.

## Failure matrix

| Failure | Detection | Response | Test |
|---|---|---|---|
| Policy branch order changes | ordered fixture records branch trace | fail test before merge | TM-085-01 |
| Two policies return conflicting input mutations | merge validator | deny with conflict diagnostic | TM-085-02 |
| Dispatcher import fails | hook startup error | fail-closed for gate; diagnostic for cap | TM-085-03 |
| Old and new entries both registered | realpath scan | registration test fails | TM-085-04 |
| Subagent self-check passes but final fence is wrong | SubagentStop validator | retry/NEED_HUMAN, no PASS | TM-085-05 |
| State write occurs twice | idempotency key | one receipt/evidence mutation | TM-085-06 |
| Bash output cap raises | dump/shaping fixture | full dump retained; bounded fallback | TM-085-07 |
| Unknown tool/event | normalized branch resolver | explicit diagnostic, no implicit gate bypass | TM-085-08 |
| Stop sees stale evidence | shared identity service | block with stale diagnostic | TM-085-09 |

## Replacement / sunset

### A — code

| Устаревает | Замена | Policy |
|---|---|---|
| duplicated pretool deny algorithms | `pretool_policy.py` | delete duplicate implementation in-epic |
| duplicated verdict/evidence plumbing | `gate_runtime.py` | delete duplicate plumbing; preserve event-specific semantics |
| duplicated posttool routing | `posttool_policy.py` | delete duplicate routing |

### B — entrypoints

| Устаревает | Замена | Policy |
|---|---|---|
| separate registered pretool commands | one canonical `pretool-dispatch.py` | delete registrations and wrappers after parity |
| separate registered posttool commands | one canonical `posttool-dispatch.py` | delete registrations and wrappers after parity |

### C — fallback/soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| silent exception → allow in gate branch | typed fail-closed diagnostic | delete in-epic |
| agent self-check treated as runtime proof | independent stop validation | delete any bypass prose |
| dual wrapper/canonical route | manifest-owned canonical path | delete all active duplicate refs |

### I — instruction/reference

| Устаревает | Замена | Policy |
|---|---|---|
| docs naming removed individual pre/post hooks as independent registration | event dispatcher contract | delete active stale refs |
| advice to merge all lifecycle events | event-specific boundary model | prohibit in active docs |

## Stages

### Stage 1 — baseline inventory and characterization (Red)

- Freeze current registration matrix from manifest and settings, including realpath, matcher, timeout and response mutation ownership.
- Add table-driven fixtures for every registered event and representative tool type.
- Capture current state/evidence/dump side effects and diagnostic codes as parity expectations.
- Add a test that explicitly proves `SubagentStart`, `SubagentStop` and `Stop` are distinct boundaries.

**Done when:** baseline fixtures fail only for intentionally missing dispatcher APIs and document all current branches.

### Stage 2 — shared typed runtime services

- Define normalized context/result types for event, tool, session, identity, decision and diagnostics.
- Extract pure identity matching, boundary validation, verdict extraction, retry classification and evidence recording without changing behavior.
- Ensure service APIs cannot accept manual mutable state as verifier proof.
- Add unit tests for positive, malformed, stale, mismatch and duplicate inputs.

**Done when:** old hooks can consume shared services and all service tests are green.

### Stage 3 — PreToolUse dispatcher

- Implement ordered pretool branch registry with explicit handlers for project/finish boundary, Agent/Task, Bash, Write/Edit/NotebookEdit and generic tools.
- Preserve current mutation rules: normalized agent input, model/isolation policy, no runner-owned CLI, protected files and finish boundary.
- Define conflict handling for multiple updated input proposals; no last-writer-wins behavior.
- Switch generated registration to one canonical pretool dispatcher after parity tests pass.

**Done when:** all pretool parity tests pass and duplicate pretool registrations are absent.

### Stage 4 — PostToolUse dispatcher

- Implement disjoint Agent/Task and Bash handlers behind one posttool entrypoint.
- Preserve `in_flight` release, verdict/evidence recording, repair handling, Bash dump path and bounded output shaping.
- Make side effects idempotent for repeated PostToolUse delivery.
- Switch generated registration to one canonical posttool dispatcher after parity tests pass.

**Done when:** Agent and Bash posttool fixtures match baseline and full output is recoverable.

### Stage 5 — Gate boundary integration

- Rewire `SubagentStart`, `SubagentStop` and `Stop` to shared services without merging their entrypoints.
- Keep agent pre-emit validation as an advisory protocol step and external SubagentStop validation as authoritative runtime enforcement.
- Make Stop and mb-finish consume the same typed evidence/status validator, preserving fail-closed behavior.
- Add regression tests for forged PASS, wrong identity, stale receipt, schema retry exhaustion and valid PASS.

**Done when:** all gate boundary tests pass and no path treats self-check alone as proof.

### Stage 6 — registration/materialization cutover

- Update manifest materialization rules and committed settings through the canonical generator.
- Remove active old pre/post registration entries and stale references; keep wrappers only if an external runtime contract requires them and mark them non-registered.
- Run realpath uniqueness and reference graph checks for every event/matcher.
- Verify Claude and Codex materialization resolve the same event semantics.

**Done when:** generated settings contain the target dispatcher matrix, no duplicate active entry exists and runtime-sync is green.

### Stage 7 — migration cleanup and regression proof

- Remove duplicate policy functions and obsolete compatibility branches whose callers are gone.
- Update active instructions/tests to the dispatcher contract; preserve historical audit files as history.
- Run targeted hook suite, full hub suite and a loop smoke covering Agent → SubagentStop → Stop.
- Record before/after process-entry count and branch coverage evidence.

**Done when:** sunset scan is empty for active callers, all AC+/AC− are evidenced and the next workflow can consume the new canonical map.

## QA consumes

| ID | Priority | Scenario | Command | Expected | Maps |
|---|---:|---|---|---|---|
| TM-085-01 | P0 | pretool branch ordering | `bin/pytest harness/hooks/tests/test_hook_dispatch.py -q` | deterministic trace | FR-002 |
| TM-085-02 | P0 | conflicting updated input | targeted pytest | deny, no partial mutation | FR-002/003 |
| TM-085-03 | P0 | dispatcher import failure | targeted hook subprocess test | gate fail-closed | NFR-003 |
| TM-085-04 | P0 | registration duplicate scan | `bin/pytest harness/hooks/tests/test_hook_registration_consolidation.py -q` | zero duplicate realpaths | FR-008 |
| TM-085-05 | P0 | self-check vs final transcript | SubagentStop fixture | malformed/mismatch not PASS | FR-006/009 |
| TM-085-06 | P0 | repeated PostToolUse | targeted pytest | one state/evidence mutation | FR-012/NFR-004 |
| TM-085-07 | P1 | noisy Bash output | output-cap fixture | full dump exists, output bounded | FR-004/NFR-005 |
| TM-085-08 | P1 | unknown event/tool | dispatch fixture | typed diagnostic, no bypass | FR-010/NFR-003 |
| TM-085-09 | P0 | stale receipt at Stop | stop-gate fixture | block with stale code | FR-007 |
| TM-085-10 | P0 | valid verifier PASS | mb-finish/stop integration test | finish still succeeds | AC-5 |
| TM-085-11 | P1 | Claude/Codex materialization | runtime-sync + parity tests | same canonical matrix | FR-008 |
| TM-085-12 | P1 | full hub regression | `bin/pytest -q --tb=line` | PASS | AC-7 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| Product probe | L3 | done | this plan §Product probe |
| Existing overlap audit | L3 | done | T-HUB-063/065/077/079 dependency map |
| Eng spine | L2+ | done | route map, decision merge contract, failure matrix |
| Replacement/sunset | required | done | A/B/C/I tables |
| QA consumes | required | done | TM-085-01…12 |
| Independent test | required | done | registration + parity + gate integration |
| Open CRITICAL | required | none | no unresolved `[НУЖНО УТОЧНИТЬ: CRITICAL]` |

## Dependency and rollout policy

1. Do not cut over dispatcher registrations before T-HUB-065 has established canonical realpath materialization.
2. Do not consolidate evidence plumbing before T-HUB-063/T-HUB-077 define authoritative SubagentStop receipt semantics.
3. Do not change retry/lease behavior in this epic; consume T-HUB-079 lifecycle APIs.
4. If a dependency is not complete, implement only characterization/shared pure services and leave registration cutover pending; never create a parallel active route.
5. Rollback is registration-level: restore the last generated settings matrix and retain shared-service tests; never disable Stop/SubagentStop gates.

## Appetite

| Поле | Значение |
|---|---|
| `timebox_days` | 4 |
| `cut_list` | provider-specific stream filters; UI/metrics dashboard; cross-runtime lease redesign; merging lifecycle events |
| `risk_budget` | no gate relaxation; no state schema migration without dependency receipt |

## Independent Test

PASS requires all of the following:

1. Registered command count decreases for pre/post tool events while lifecycle event count and gate boundaries remain unchanged.
2. Positive and negative parity fixtures match baseline decisions and side effects.
3. Forged/manual/stale evidence is rejected by external SubagentStop/Stop validation.
4. Generated settings and manifest contain no duplicate active realpaths or stale removed references.
5. Full hub suite and loop smoke remain green.

## Следующий режим

→ **BACK DECOMPOSE T-HUB-085-hook-event-dispatcher-consolidation** after hard dependencies are ready; current `activeContext` remains owned by T-HUB-081 until its workflow finishes.
