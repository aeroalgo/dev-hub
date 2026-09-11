# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-085-hook-event-dispatcher-consolidation  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-11  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная production capability с outcome-first goal, полным delta layer, plan contract, TDD внутри шага и измеримыми checkpoints. Layout v2: shards находятся в `yaml/steps/`; `decompose-index.yaml` — единственный источник статуса.

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | Структура и атомарность decompose-артефакта; сессионный skill, не передаётся в IMPLEMENT. |
| BACK Impl Core | `tdd`, `python-testing-patterns`, `modern-python`, `python-anti-patterns` присутствуют в каждом production shard. |
| Situational | На каждом shard выбраны только skills из BACK allowlist по surface: async, type-safety, resilience, observability, configuration. |

**Per-step:** итоговый `skills.impl` хранится в каждом YAML и является источником обязательных Read для BACK IMPLEMENT. Нет UI; `needs_creative: "no"` во всех шагах.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR / US → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` уже в `roadmap-*.queue.yaml`.

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как runtime, я хочу один pre-tool entrypoint на событие, чтобы policy checks выполнялись детерминированно и без конфликтующих ответов. | s01, s03 | s01 context dispatch, s03 pretool canonical entrypoint |
| US-002 | Как runtime, я хочу один post-tool entrypoint на событие, чтобы agent state и Bash output shaping не дублировали dispatcher plumbing. | s04 | s04 posttool-dispatch with disjoint agent/bash handlers |
| US-003 | Как gate, я хочу общий pure validator для schema/identity/evidence, но отдельный `SubagentStop` boundary. | s02, s05 | s02 pure helpers in gate_runtime.py, s05 boundary wiring |
| US-004 | Как оператор, я хочу видеть, какой dispatch branch сработал и почему был deny/retry. | s01, s02, s03, s04, s05 | Structured diagnostics across all dispatch handlers |
| US-005 | Как CI, я хочу запрещать возвращение duplicate active hook commands и мёртвых dispatcher references. | s06, s07 | s06 manifest/settings scan, s07 legacy purge |
| FR-001 | Ввести event-specific dispatch layer с отдельными входами для `pretool`, `posttool`, `subagent_start`, `subagent_stop` и `stop`; dispatcher не смешивает события и не скрывает отказ. | s01, s03, s04, s05 | Dispatch architecture and event entrypoints |
| FR-002 | `PreToolUse` сохраняет порядок policy: project boundary → finish boundary → tool-specific policy; первый deny является итогом, allow возвращает все нужные `updatedInput` mutations. | s01, s03 | s01 execution ordering logic, s03 pretool policy adapters |
| FR-003 | `PreToolUse` dispatcher маршрутизирует Agent/Task, Bash, Write/Edit/NotebookEdit и generic tools по `tool_name`, сохраняя текущие matcher semantics. | s03 | Tool routing in pretool-dispatch.py |
| FR-004 | `PostToolUse` dispatcher маршрутизирует Agent/Task и Bash; agent state/evidence и output-cap не вызывают друг друга и сохраняют прежние payload response fields. | s04 | Disjoint posttool handlers in posttool-dispatch.py |
| FR-005 | Общие pure services для `state identity`, `verdict extraction`, `boundary validation`, `evidence recording` и `diagnostic codes` имеют один контракт и используются hooks/CLI без копирования алгоритма. | s02, s05 | gate_runtime.py shared typed helpers |
| FR-006 | `SubagentStart` остаётся отдельной точкой contract injection и drift deny; `SubagentStop` остаётся отдельной точкой фактического transcript validation. | s02, s05 | Distinct lifecycle hooks with external validation |
| FR-007 | `Stop` остаётся отдельным final gate и использует общий read-only status/evidence service, но не доверяет состоянию, созданному только parent agent. | s02, s05 | Final stop gate verification with shared evidence service |
| FR-008 | Manifest/materializer и committed settings регистрируют ровно один canonical command на `(event, matcher, realpath)`; dispatcher migration не создаёт dual path. | s06, s07 | Manifest consolidation and materialization |
| FR-009 | Self-check агента `validate-boundary` и внешний `SubagentStop` validation сохраняются как два разных trust boundary; разрешается общий library implementation, но не удаление внешней проверки. | s02, s05 | Dual trust boundary enforcement |
| FR-010 | Каждый dispatch branch имеет deterministic diagnostic при deny/retry/error; исключение не превращается в silent allow. | s01, s02, s03, s04 | Fail-closed typed diagnostics |
| FR-011 | Старые entrypoints либо становятся тонкими compatibility wrappers с одним canonical implementation, либо удаляются внутри эпика; вечный dual implementation запрещён. | s03, s04, s06, s07 | Progressive cutover and final purge |
| FR-012 | Тесты проверяют parity positive/negative side effects, subprocess registration count, ordering, idempotency и fail-closed behavior. | s01, s02, s03, s04, s05, s06, s07 | Comprehensive parity and regression test suites |
| NFR-001 | Снижение числа registered command entries минимум с текущих 11 до целевого event-specific набора без снижения числа lifecycle boundaries. | s06, s07 | Manifest reduction and settings materialization |
| NFR-002 | Dispatcher branch должен быть синхронным и bounded; не добавлять сетевой/LLM вызов в authorization path. | s01, s03, s04, s05 | Synchronous bounded pure logic |
| NFR-003 | Все deny/retry decisions остаются fail-closed; неизвестный event/tool/branch не получает implicit allow. | s01, s02, s03, s04, s05 | Fail-closed exception handling |
| NFR-004 | State mutation выполняется только один раз за hook event и остаётся idempotent по `(session_id, tool_use_id, agent_type, verdict)`. | s02, s04 | Idempotent evidence recording and state mutation |
| NFR-005 | Полный вывод Bash по-прежнему сохраняется до сокращения, если включён output cap; dispatcher не теряет dump path. | s04 | Raw dump preservation before output capping |
| NFR-006 | Новые публичные helper API покрываются typed input/output и не принимают произвольные state dict как proof PASS. | s02, s05 | Strict typing in gate_runtime.py |
| AC+ #1 | На `PreToolUse` зарегистрирован один canonical dispatcher; Agent/Bash/Write/generic fixtures получают те же allow/deny и updated input semantics. | s01, s03, s06 | Canonical pretool-dispatch.py |
| AC+ #2 | На `PostToolUse` зарегистрирован один canonical dispatcher; Agent verdict/evidence и Bash output cap сохраняют текущие side effects. | s04, s06 | Canonical posttool-dispatch.py |
| AC+ #3 | `SubagentStart`, `SubagentStop` и `Stop` остаются раздельными entries и проходят отдельные event tests. | s05 | Independent lifecycle entrypoints |
| AC+ #4 | Внешний `SubagentStop` отвергает malformed fence, schema mismatch, ownership mismatch и stale identity даже если агентский self-check был успешен. | s02, s05 | Strict external transcript verification |
| AC+ #5 | `Stop` не принимает state-only/manual PASS и не разрешает finish без обязательного gate. | s02, s05 | Stop gate requires valid verifier evidence |
| AC+ #6 | Duplicate realpath scan даёт ноль active duplicates; old entrypoints не вызываются из settings/manifest. | s06, s07 | Unique realpath validation |
| AC+ #7 | Все старые registered hook behavior tests зелёные либо заменены parity tests с тем же acceptance. | s06, s07 | Suite green with new dispatchers |
| AC+ #8 | Diagnostics позволяют отличить `deny`, `retry`, `recorded`, `output_capped`, `stale` и `infrastructure_failure`. | s01, s02, s03, s04, s05 | Typed diagnostic codes |
| AC− #1 | Нельзя получить allow, если любой обязательный pretool policy вернул deny. | s01, s03 | Short-circuit on first deny |
| AC− #2 | Нельзя получить PASS только потому, что parent записал verdict/state вручную. | s02, s05 | Guard against manual state forge |
| AC− #3 | Нельзя заменить фактический transcript SubagentStop результатом, который агент проверил сам. | s02, s05 | External verification enforcement |
| AC− #4 | Нельзя запустить одновременно две managed gate branches для одной identity. | s02, s05 | Identity lock checks |
| AC− #5 | Нельзя зарегистрировать одновременно wrapper и canonical dispatcher на одном event/matcher. | s06, s07 | Registration uniqueness |
| AC− #6 | Нельзя потерять полный Bash dump из-за dispatcher exception. | s04 | Safe raw dump saving before output shaping |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN | Measurable closure |
| :--- | :--- | :--- | :--- |
| Stage 1 — baseline inventory and characterization (Red) | plan §Stages (Stage 1) | s01 | Table-driven fixtures for routing, order, merge, fail-closed diagnostics |
| Stage 2 — shared typed runtime services | plan §Stages (Stage 2) | s02 | Pure helpers in gate_runtime.py for boundary, identity, verdict, evidence |
| Stage 3 — PreToolUse dispatcher | plan §Stages (Stage 3) | s03 | Canonical pretool-dispatch.py with pure pretool_policy adapters |
| Stage 4 — PostToolUse dispatcher | plan §Stages (Stage 4) | s04 | Canonical posttool-dispatch.py with disjoint agent/bash handlers |
| Stage 5 — Gate boundary integration | plan §Stages (Stage 5) | s05 | SubagentStart, SubagentStop, Stop rewired to gate_runtime.py |
| Stage 6 — registration/materialization cutover | plan §Stages (Stage 6) | s06 | Manifest and settings consolidated; duplicate realpath scan green |
| Stage 7 — migration cleanup and regression proof | plan §Stages (Stage 7) | s07 | Legacy hooks deleted, zero prod callers verified, hub regression suite green |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги | Почему это production outcome |
| :--- | :--- | :--- |
| Снижение overhead на запуск subprocess без потери надежности | s01, s03, s04, s06 | PreToolUse и PostToolUse объединяют связанные проверки в единые входы, снижая число команд с 11+ до канонического набора. |
| Детерминированный порядок pretool проверок с первым deny | s01, s03 | Project boundary -> finish boundary -> tool policy выполняются строго последовательно. |
| Авторитетная независимая проверка gate на SubagentStop | s02, s05 | Внешний hook проверяет реальный transcript и отвергает поддельный/ручной PASS. |
| Идемпотентность мутаций и сохранение сырого дампа Bash | s02, s04 | Повторный posttool не плодит дубликаты, а bash dump сохраняется до сокращения вывода. |
| Полное удаление устаревших entrypoints и отсутствие dual-path | s06, s07 | Manifest и settings переведены на канонические диспетчеры, старые файлы удалены. |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/hooks/agent-pretool.py` | A | `harness/hooks/pretool_policy.py` | s07 | no | Deleted after s06 cutover |
| `harness/hooks/bash-pretool.py` | A | `harness/hooks/pretool_policy.py` | s07 | no | Deleted after s06 cutover |
| `harness/hooks/write-pretool.py` | A | `harness/hooks/pretool_policy.py` | s07 | no | Deleted after s06 cutover |
| `harness/hooks/finish-boundary-pretool.py` | A | `harness/hooks/pretool_policy.py` | s07 | no | Deleted after s06 cutover |
| `harness/hooks/agent-posttool.py` | A | `harness/hooks/posttool_policy.py` | s07 | no | Deleted after s06 cutover |
| `duplicated verdict/evidence plumbing` | A | `harness/hooks/gate_runtime.py` | s07 | no | Delete duplicate plumbing; preserve event-specific semantics |
| `separate registered pretool commands` | B | `harness/hooks/pretool-dispatch.py` | s06, s07 | no | Replaced in manifest/settings |
| `separate registered posttool commands` | B | `harness/hooks/posttool-dispatch.py` | s06, s07 | no | Replaced in manifest/settings |
| `silent exception → allow in gate branch` | C | typed fail-closed diagnostic | s01, s02, s07 | yes | Replaced by fail-closed envelope |
| `agent self-check treated as runtime proof` | C | independent stop validation | s07 | no | Delete any bypass prose |
| `dual wrapper/canonical route` | C | manifest-owned canonical path | s06, s07 | no | Delete all active duplicate refs |
| `docs naming removed individual pre/post hooks` | I | event dispatcher contract | s06, s07 | no | Updated in documentation |
| `advice to merge all lifecycle events` | I | event-specific boundary model | s07 | no | Prohibit in active docs |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-event-dispatch-abstractions.yaml](../yaml/steps/s01-event-dispatch-abstractions.yaml) | [s01…](../../implement/T-HUB-085-hook-event-dispatcher-consolidation/s01-event-dispatch-abstractions.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-shared-gate-and-evidence-service.yaml](../yaml/steps/s02-shared-gate-and-evidence-service.yaml) | [s02…](../../implement/T-HUB-085-hook-event-dispatcher-consolidation/s02-shared-gate-and-evidence-service.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-pretool-dispatcher-and-policy-adapters.yaml](../yaml/steps/s03-pretool-dispatcher-and-policy-adapters.yaml) | [s03…](../../implement/T-HUB-085-hook-event-dispatcher-consolidation/s03-pretool-dispatcher-and-policy-adapters.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-posttool-dispatcher-and-output-shaping.yaml](../yaml/steps/s04-posttool-dispatcher-and-output-shaping.yaml) | [s04…](../../implement/T-HUB-085-hook-event-dispatcher-consolidation/s04-posttool-dispatcher-and-output-shaping.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-gate-boundary-lifecycle-integration.yaml](../yaml/steps/s05-gate-boundary-lifecycle-integration.yaml) | [s05…](../../implement/T-HUB-085-hook-event-dispatcher-consolidation/s05-gate-boundary-lifecycle-integration.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-manifest-consolidation-and-materialization-cutover.yaml](../yaml/steps/s06-manifest-consolidation-and-materialization-cutover.yaml) | [s06…](../../implement/T-HUB-085-hook-event-dispatcher-consolidation/s06-manifest-consolidation-and-materialization-cutover.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-legacy-fallback-purge.yaml](../yaml/steps/s07-legacy-fallback-purge.yaml) | [s07…](../../implement/T-HUB-085-hook-event-dispatcher-consolidation/s07-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |