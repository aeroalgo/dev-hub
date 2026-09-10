# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-091-gate-identity-sot-consolidation
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml)
**Дата:** 2026-09-10
**Режим:** BACK DECOMPOSE

Нарезка реализует единый Single Source of Truth (GateIdentity SoT) для Claude Code и Codex CLI, устраняя конфликтующие источники session/step/epic identity и поштучный симптоматический coerce ladder. Всего 7 sNN: ядро SoT API, атомарная инициализация и Claude pretool bind, Claude start inject + stop strict assertion, Codex spawn observe prompt rewrite + pending bind, Codex stop transport_bind + удаление coerce ladder, выверка instruction surfaces (Kind I), и финальный sunset purge (A+B+C+I).

## Requirements coverage

| Req ID | Plan FR text | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Ввести единый API GateIdentity SoT: freeze, expected, inject_text, bind_spawn_gate, assert_fence. | s01 | Ядро API SoT в loop/gate_identity.py + session_finalize. |
| FR-002 | prepare_session атомарно: bind session_id + freeze session_start_identity + bind_spawn_gate. | s02 | Атомарный freeze и mirror в spawn-gate при подготовке сессии. |
| FR-003 | Все ownership readers используют только SoT expected / current_gate_identity через SoT. | s01, s02, s03, s04, s05 | Исключение чтения сырого projection.step в обход freeze. |
| FR-004 | Claude SubagentStart: inject_text(SoT) в additionalContext. | s03 | Доставка SoT identity в child до начала работы. |
| FR-005 | Claude PreToolUse: mark_in_flight + bind_spawn_gate(SoT) атомарно. | s02 | Предотвращение race condition при spawn. |
| FR-006 | Codex spawn_agent observe: rewrite prompt с inject_text(SoT) + bind pending thread. | s04 | Перехват и доставка SoT блока в prompt до wait. |
| FR-007 | Codex SubagentStop: transport_bind fence := SoT через API; agent_id mismatch fail. | s05 | Транспортный bind полей из SoT, agent_id остаётся строгим. |
| FR-008 | Claude SubagentStop: strict — расхождение session/epic/step -> semantic_ownership_mismatch. | s03 | Строгая валидация без schema-retry. |
| FR-009 | Удалить продуктовый поштучный coerce block в subagent-stop.py; переписать тесты coerce. | s05, s07 | Полный демонтаж if-ladder coerce и обновление тестов. |
| FR-010 | Post-wait SubagentStart для Codex не считается delivery inject (mark-only). | s04 | Запрет ложной симметрии lifecycle. |
| FR-011 | Kind I: agent/verify prompts — IDs из GATE_IDENTITY / литералы фазы согласованы с SoT. | s06 | Промпты субагентов не учат «угадывать sNN с эпика». |
| FR-012 | DSH не расширять; существующие passthrough не ломать. | s06, s07 | DSH out of scope; сохранение существующих thin адаптеров. |
| FR-013 | session_start_payload / PromptScope не становятся вторым SoT в этом эпике. | s01 | Чёткое разделение ответственности с T-HUB-071. |
| FR-014 | Wire-complete: dual path coerce+bind запрещён после эпика. | s05, s07 | Запрет fallback-сохранения старого coerce ladder. |
| SC-001 | Ownership step при freeze≠armed всегда freeze. | s01 | pytest test_freeze_and_expected_ignore_armed. |
| SC-002 | Claude stale step → ownership NEED_HUMAN. | s03 | pytest test_subagent_stop_claude_strict_mismatch. |
| SC-003 | Codex wrong fence IDs → no ownership NEED_HUMAN; IDs=SoT. | s05 | pytest test_codex_fence_binds_to_sot. |
| SC-004 | Codex spawn prompt contains GATE_IDENTITY before child. | s04 | pytest test_spawn_prompt_contains_gate_identity. |
| SC-005 | Нет per-field coerce ladder в stop. | s05, s06, s07 | rg scan + grep_control. |
| SC-006 | prepare leaves spawn-gate mirror == SoT. | s02 | pytest test_prepare_mirrors_spawn_gate. |
| US-001 | Как loop, я читаю ownership только из GateIdentity SoT. | s01 | Юнит-тесты SoT API. |
| US-002 | Как Claude verify child, я вижу GATE_IDENTITY = SoT до работы. | s03 | Доставка в additionalContext. |
| US-003 | Как Claude stop, чужой step_id → NEED_HUMAN ownership. | s03 | semantic_ownership_mismatch exit 2. |
| US-004 | Как Codex parent, spawn_agent prompt получает GATE_IDENTITY до child. | s04 | Rewrite prompt на spawn observe. |
| US-005 | Как Codex stop, fence с s05/foreign epic не даёт ownership NEED_HUMAN; identity := SoT. | s05 | transport_bind API. |
| US-006 | Как инженер, я не вижу поштучный coerce в stop. | s05, s07 | Чистый код без per-field ladder. |
| US-007 | Как runner, freeze+mirror spawn-gate атомарны на prepare. | s02 | Атомарный helper в prepare_session. |
| AC+ #1 | GateIdentity SoT API — единственный ownership reader для Claude/Codex gate fences. | s01, s03, s05 | Все fence-проверки идут через GateIdentity. |
| AC+ #2 | Claude: inject pre-child + strict ownership. | s03 | SubagentStart inject + SubagentStop strict. |
| AC+ #3 | Codex: spawn-time SoT delivery + transport_bind на stop. | s04, s05 | Rewrite prompt + transport_bind. |
| AC+ #4 | Per-field coerce удалён; тесты переписаны. | s05, s07 | Удаление ladder и обновление test_codex_session_ownership_coerce.py. |
| AC+ #5 | prepare атомарно freeze+mirror; Claude spawn mark+bind. | s02 | Атомарные функции в loop/session_finalize.py и agent-pretool.py. |
| AC+ #6 | Kind I prompts согласованы. | s06 | Промпты субагентов берут IDs из GATE_IDENTITY / фазы. |
| AC+ #7 | DSH не в scope и не «случайно» расширен требованиями. | s06, s07 | DSH не трогается. |
| AC− #1 | Нет dual path coerce+SoT bind. | s05, s07 | Проверено grep_control. |
| AC− #2 | Нет ownership от сырого projection.step в обход freeze. | s01, s02 | Все ownership checks идут через freeze. |
| AC− #3 | Нет schema-retry на ownership. | s03, s05 | Exit 2 / fail-closed без schema-retry. |
| AC− #4 | Нет «Codex post-wait SubagentStart = inject». | s04 | Documented mark-only behavior. |
| AC− #5 | Нет нового DSH adapter scope. | s06, s07 | DSH passthrough unchanged. |
| AC− #6 | Нет второго SoT в PromptScope/resolve_session_identity как fence ownership. | s01 | Разграничение scope с T-HUB-071. |

## Stages coverage

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| GateIdentity SoT API core & invariant tests | plan §HOW, TM-001, FR-001, FR-003, US-001, SC-001 | s01 |
| Atomic prepare_session freeze + Claude pretool bind | plan §WHAT / §HOW, TM-007, FR-002, FR-005, US-007, SC-006 | s02 |
| Claude SubagentStart inject + SubagentStop strict assertion | plan §WHAT, TM-002, TM-005, FR-004, FR-008, US-002, US-003, SC-002 | s03 |
| Codex spawn prompt rewrite + pending thread bind | plan §WHAT, TM-004, FR-006, FR-010, US-004, SC-004 | s04 |
| Codex SubagentStop transport_bind + coerce ladder removal | plan §WHAT / §Replacement, TM-003, TM-005, FR-007, FR-009, FR-014, US-005, US-006, SC-003, SC-005 | s05 |
| Kind I prompts & instruction surfaces alignment | plan §Replacement / sunset (I), FR-011, FR-012 | s06 |
| Full sunset inventory scan, grep_control & regression check | plan §Replacement / sunset (A, B, C, I), TM-006, TM-001..TM-007 | s07 |
| Full suite verification | TM-001..TM-007 | BACK QA после IMPLEMENT |

## Outcome map

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Единый SoT GateIdentity API для управления ownership identity | s01, s02, s03, s04, s05 |
| Атомарная фиксация freeze и mirror spawn-gate без race condition | s02 |
| Claude pre-child inject и строгая ownership валидация (strict) | s03 |
| Codex spawn-time доставка SoT через prompt rewrite и pending bind | s04 |
| Codex transport_bind на stop и полное удаление поштучного coerce ladder | s05, s07 |
| Инструкции субагентов Kind I согласованы с SoT (IDs из GATE_IDENTITY / фазы) | s06 |
| Нулевые prod callers устаревшего coerce ladder и fallback-путей | s07 |
| Full suite test matrix TM-001..TM-007 | BACK QA handoff после s07 |
| Out of scope: DSH adapter expansion, PromptScope redesign (071), Supervisor (086) | — |

## Replacement cleanup

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/hooks/subagent-stop.py` per-field Codex coerce if-ladder | A | `GateIdentity.bind_fence` / `assert_fence(policy=transport_bind)` | s05, s07 | no | Удалить поштучный ladder session_id/step_id/epic_id. |
| Raw `gate_identity(...)` reads without overlay on ownership paths | A | `GateIdentity.expected` / `current_gate_identity` -> SoT | s01, s02, s07 | no | Все ownership checks идут через freeze SoT. |
| `subagent-start._gate_session_id` duplicate | A | `_lib.gate_session_id` / SoT | s03, s07 | no | Использовать единый helper. |
| `loop/tests/test_codex_session_ownership_coerce.py` old contract asserts | A | rewrite on new SoT transport_bind API | s05, s07 | no | Тесты переписаны на проверку SoT bind. |
| `Codex post-wait SubagentStart treated as child inject delivery` | A | mark-only post-wait lifecycle; spawn-time prompt inject | s04, s07 | no | Post-wait SubagentStart не является delivery inject. |
| `entrypoints/deploy (n/a — те же hooks/CLI)` | B | `greenfield n/a for deploy` | none | no | `same hooks/CLI` |
| «если rewrite недоступен -> оставить coerce ladder forever» | C | documented Codex transport_bind policy | s05, s07 | no | Запрет fallback dual-path. |
| Silent accept LLM fence IDs when SoT present (Claude) | C | strict mismatch exit 2 | s03, s07 | no | Строгая проверка для Claude. |
| Ownership from live projection after finish without freeze | C | freeze-only expected | s01, s02, s07 | no | Запрет чтения live projection в обход freeze. |
| Agent prompts «подставь любой step_id / sNN с эпика» | I | IDs из GATE_IDENTITY / литерал фазы | s06, s07 | no | Выверка instruction surfaces. |
| `Collaboration text implying post-wait start = inject` | I | explicit mark-only lifecycle wording; inject only at spawn | s06, s07 | no | Текст явно разделяет post-wait mark-only и spawn-time inject. |
| Docs/comments «Codex coerce session only» | I | transport_bind SoT policy | s06, s07 | no | Обновление комментариев и документации. |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-gate-identity-sot-api.yaml](../yaml/steps/s01-gate-identity-sot-api.yaml) | [s01-gate-identity-sot-api.yaml](../../implement/T-HUB-091-gate-identity-sot-consolidation/s01-gate-identity-sot-api.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-atomic-prepare-and-pretool-bind.yaml](../yaml/steps/s02-atomic-prepare-and-pretool-bind.yaml) | [s02-atomic-prepare-and-pretool-bind.yaml](../../implement/T-HUB-091-gate-identity-sot-consolidation/s02-atomic-prepare-and-pretool-bind.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-claude-inject-and-strict-stop.yaml](../yaml/steps/s03-claude-inject-and-strict-stop.yaml) | [s03-claude-inject-and-strict-stop.yaml](../../implement/T-HUB-091-gate-identity-sot-consolidation/s03-claude-inject-and-strict-stop.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-codex-spawn-rewrite-and-bind.yaml](../yaml/steps/s04-codex-spawn-rewrite-and-bind.yaml) | [s04-codex-spawn-rewrite-and-bind.yaml](../../implement/T-HUB-091-gate-identity-sot-consolidation/s04-codex-spawn-rewrite-and-bind.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-codex-stop-transport-bind-and-coerce-removal.yaml](../yaml/steps/s05-codex-stop-transport-bind-and-coerce-removal.yaml) | [s05-codex-stop-transport-bind-and-coerce-removal.yaml](../../implement/T-HUB-091-gate-identity-sot-consolidation/s05-codex-stop-transport-bind-and-coerce-removal.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s06** | [s06-instruction-surfaces-kind-i.yaml](../yaml/steps/s06-instruction-surfaces-kind-i.yaml) | [s06-instruction-surfaces-kind-i.yaml](../../implement/T-HUB-091-gate-identity-sot-consolidation/s06-instruction-surfaces-kind-i.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s07** | [s07-legacy-fallback-purge.yaml](../yaml/steps/s07-legacy-fallback-purge.yaml) | [s07-legacy-fallback-purge.yaml](../../implement/T-HUB-091-gate-identity-sot-consolidation/s07-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |

**Следующий режим после завершения дерева:** BACK ANALYZE. `ANALYZE deferred` не используется.
