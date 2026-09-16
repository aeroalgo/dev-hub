# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-106-dsh-runtime-full-purge
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-16
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (BACK: один prod-модуль или один test-file/domain-area). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](.cursor/templates/decompose/epic-step.yaml).

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | структура шагов, атомарность |
| `architecture-patterns` | соблюдение границ модулей при удалении рантайма |
| `python-testing-patterns` | написание deny-тестов и очистка тест-сьюта |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как оператор loop, я хочу, чтобы поддерживались только Claude Code и Codex, чтобы не поддерживать DSH. | s01, s02, s03, s05, s07, s08 | Полноценная поддержка только claude и codex. |
| US-002 | Как разработчик hub, я хочу отсутствие дерева `dsh/` и DSH-адаптера, чтобы не тянуть Cordis/plugins. | s02, s04, s05, s07, s08 | Дерево dsh/ и DshAdapter полностью удалены. |
| US-003 | Как агент по AGENTS/CLAUDE, я не должен получать инструкцию выбирать DSH runtime. | s06, s08 | Kind I инструкции вычищены. |
| FR-001 | Система должна отвергать runtime id `dsh` (и бывшие aliases на dsh) на CLI, env и factory adapter с fail-closed ошибкой. | s01, s02, s03, s05, s08 | Отказ на CLI, env и в фабрике адаптеров. |
| FR-002 | Система должна иметь registry SoT только для `claude` и `codex` (плюс documented alias `claude-code`). | s02, s08 | Реестр рантаймов содержит только claude и codex. |
| FR-003 | Система должна удалить пакет/дерево `dsh/` включая scripts install-profiles / install-cc-hooks / which-dsh. | s05, s08 | Удаление файлового дерева dsh/. |
| FR-004 | Система должна удалить `DshAdapter` и все prod call sites / imports. | s02, s03, s04, s08 | Удаление DshAdapter и ссылок на него. |
| FR-005 | Система должна убрать machine field/API `dsh_preset` / `get_dsh_preset` из live phase arm path (delete symbol или fail если передано — без no-op keep). | s03, s04, s08 | Удаление get_dsh_preset и конфигурационного поля. |
| FR-006 | Система должна удалить harness DSH-only surfaces: `dsh_stream_filter.py`, DSH abort/mismatch branches, manifest dsh blocks, `DSH_HOOKS_BRIDGE` wiring. | s04, s08 | Удаление хуков и манифестов DSH. |
| FR-007 | Система должна удалить или переписать тесты, которые требуют DSH-контракт (включая `test_loop_dsh_dispatch.py`, `test_dsh_e2e_smoke.py` и кейсы `runtime="dsh"`). | s07, s08 | Очистка и переписывание тестового набора. |
| FR-008 | Система должна переписать live Kind I (AGENTS/CLAUDE/instructions/README/LOOP-RUNTIMES/runbooks/architecture index) так, чтобы DSH не был supported runtime; удалить `DSH.md` и `docs/runbooks/dsh-loop-pilot.md` и `memory-bank/architecture/dsh-runtime.md` как live surfaces. | s06, s08 | Переписывание документации и инструкций. |
| FR-009 | Misconfig / выбор dsh **не** должен молча деградировать в claude. | s01, s03, s08 | Fail-closed поведение без fallback. |
| SC-001 | `rg` prod: нет `DshAdapter` / `runtime_adapters.dsh` / registry key `dsh:` | s02, s03, s04, s08 | Подтверждение отсутствия символов в prod. |
| SC-002 | `test -d dsh` → false | s05, s08 | Проверка отсутствия каталога dsh/. |
| SC-003 | CLI/env `dsh` → fail | s01, s03, s08 | Проверка отказа при передаче dsh. |
| SC-004 | Kind I live teaching patterns = 0 | s06, s08 | Проверка отсутствия обучающих инструкций. |
| SC-005 | Targeted DSH-related suite deleted/rewritten; no restore-legacy to green | s07, s08 | Проверка тестового сьюта. |
| AC+ #1 | Registry и factory не отдают DSH adapter; `dsh` → явная ошибка. | s01, s02, s08 | Реестр и фабрика отвергают dsh. |
| AC+ #2 | Дерево `dsh/` отсутствует в репо. | s05, s08 | Каталог dsh/ удален. |
| AC+ #3 | `bin/loop` / `runtime_sync` / prepare_session не принимают `dsh` как valid choice. | s01, s03, s05, s08 | CLI и точка входа отвергают dsh. |
| AC+ #4 | Prod-код без `DshAdapter`, `get_dsh_preset` live path, `DSH_HOOKS_BRIDGE` dsh-only wiring. | s02, s03, s04, s08 | Prod-код вычищен от dsh. |
| AC+ #5 | Obsolete DSH tests удалены; mixed tests переписаны на claude/codex или deny. | s07, s08 | Тесты приведены в порядок. |
| AC+ #6 | Live Kind I не учит DSH как supported runtime; `DSH.md` и dsh-runbook/architecture dsh-runtime удалены. | s06, s08 | Документация очищена. |
| AC+ #7 | Targeted pytest green без восстановления DSH. | s07, s08 | Тесты зеленые. |
| AC− #1 | Нет второго entrypoint на роль agent-runtime через DSH. | s05, s08 | Отсутствие точки входа dsh. |
| AC− #2 | Нет soft default / silent `dsh`→`claude`. | s01, s02, s03, s08 | Запрет тихого fallback. |
| AC− #3 | Misconfig `EPIC_RUNTIME=dsh` → fail at start (non-zero / raise), не stub. | s01, s03, s08 | Запуск падает с ошибкой. |
| AC− #4 | Нет prod dual-path registry с ключом `dsh` после эпика. | s02, s08 | Реестр без дуального пути. |
| AC− #5 | Нет живых тестов, требующих DSH-контракт. | s07, s08 | Тесты не требуют dsh. |
| AC− #6 | Нет Kind I, требующих DSH как live SoT (на allowlist instruction paths). | s06, s08 | Инструкции не требуют dsh. |
| AC− #7 | Нет optional SoT «dsh available but deprecated» без follow-up ID. | s02, s03, s08 | Никаких deprecated shim без эпика. |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Characterization & deny-oracle baseline | plan.md §HOW | s01 |
| Runtime registry & adapter factory cutover | plan.md §HOW | s02 |
| Loop core call sites & config purge | plan.md §HOW | s03 |
| Harness hooks & manifest purge | plan.md §HOW | s04 |
| Repo layout & entrypoint purge (dsh/ tree) | plan.md §HOW | s05 |
| Kind I instructions & docs rewrite/delete | plan.md §HOW | s06 |
| Test suite consolidation & rewrite | plan.md §HOW | s07 |
| Legacy fallback purge & full inventory audit | plan.md §HOW | s08 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Полная ликвидация рантайма DSH из системы без оставления shims | s01, s02, s03, s04, s05, s06, s07, s08 |
| Fail-closed поведение CLI и session preparation при передаче dsh | s01, s02, s03, s05, s08 |
| Удаление всех библиотек, плагинов и профилей из dsh/ | s05, s08 |
| Очистка инструкций и документации Kind I | s06, s08 |
| Обеспечение зеленого тестового сьюта без legacy DSH | s01, s07, s08 |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `loop/runtime_adapters/dsh.py` · `DshAdapter` | A | ClaudeAdapter / CodexAdapter | s02 | no | Удаление файла и класса |
| `loop/runtime_registry.yaml` key `dsh:` | A | keys `claude`, `codex` only | s02 | no | Удаление ключа и алиасов |
| `loop.epic_transition.get_dsh_preset` · kwargs `dsh_preset` | A | phase registry без dsh_preset | s03 | no | Удаление символа и аргументов |
| `loop.prompt_builder` alias `deepseek-harness`/`deepseek`→`dsh` | A | normalize claude/codex only | s03 | no | Удаление веток dsh |
| `loop.runner.config` `runtime == "dsh"` / `DSH_HOOKS_BRIDGE` | A | non-dsh env only | s03 | no | Очистка конфигурации |
| `loop.cli.runtime_sync` choice `dsh` | A | choices `codex`, `claude`, `all` | s03 | no | Удаление dsh из choices |
| `context_loop` allowlist globs requiring `dsh/` path class | A | remove the `dsh/` path class from the allowlist | s03 | no | Удаление DSH path class из allowlist |
| Board/CLI `--runtime dsh` | B | remove `dsh` from runtime choices and reject the token | s03 | no | Удаление DSH runtime option |
| `loop.runtime.session_events` dsh-specific event normalize | A | generic/claude/codex only | s03 | no | Очистка обработки событий |
| `harness/hooks/dsh_stream_filter.py` | A | none | s04 | no | Удаление файла |
| `harness/hooks/session_resilience.py` DSH patterns / `detect_dsh_*` | A | claude/codex resilience only | s04 | no | Удаление детектора |
| `harness/hooks/_lib.py` dsh frozenset / `DSH_HOOKS_BRIDGE` | A | claude/codex runtimes only | s04 | no | Удаление dsh |
| `harness/hooks/epic/core.py` `dsh_preset` kwargs plumbing | A | remove kwargs | s04 | no | Очистка параметров |
| `harness/manifest.yaml` `dsh:` blocks | A | remove dsh blocks | s04 | no | Очистка манифеста |
| `dsh/**` (entire tree) | A | none | s05 | no | Удаление всего каталога |
| `loop/tests/test_loop_dsh_dispatch.py` | A | none | s07 | no | Удаление файла |
| `loop/tests/test_dsh_e2e_smoke.py` | A | none | s07 | no | Удаление файла |
| Mixed tests asserting `runtime=="dsh"` / `DshAdapter` | A | rewrite deny or claude/codex | s07 | no | Переписывание тестов |
| `bin/loop` case `claude\|codex\|dsh` | B | `claude\|codex` only | s05 | no | Очистка case в скрипте |
| `EPIC_RUNTIME=dsh` documented launch | B | unsupported | s06 | no | Удаление из документации |
| `./dsh/scripts/install-profiles.sh` & `install-cc-hooks.sh` | B | none | s05 | no | Удаление скриптов |
| `runtime_sync --runtime dsh` | B | `all` = claude+codex | s03 | no | Удаление опции |
| Silent dsh→claude fallback | C | fail-closed exception | s01, s02, s08 | no | Исключение тихого fallback |
| `DSH_HOOKS_BRIDGE` soft enable | C | fail-closed | s03, s04, s08 | no | Очистка env |
| Keeping registry key `dsh` «deprecated» | C | delete key | s02, s08 | no | Полное удаление ключа |
| Optional flag `allow_dsh` default off | C | remove the flag; reject dsh unconditionally | s01, s03, s08 | no | Удаление soft-enable флага |
| `DSH.md` | I | none | s06 | no | Удаление файла |
| `docs/runbooks/dsh-loop-pilot.md` | I | none | s06 | no | Удаление файла |
| `memory-bank/architecture/dsh-runtime.md` | I | none | s06 | no | Удаление файла |
| `AGENTS.md` / `CLAUDE.md` / `harness/instructions/main.md` DSH bullet | I | Claude Code / Codex only | s06 | no | Очистка инструкций |
| `README.md` agent table / DSH Runtime section | I | Claude + Codex only | s06 | no | Очистка README |
| `LOOP-RUNTIMES.md` ## DSH section | I | remove section | s06 | no | Очистка файла |
| `loop/README.md` / `loop/WORKFLOW.md` DSH mentions | I | rewrite | s06 | no | Очистка документации loop |
| `harness/instructions/spawn-hard.md` «Claude Code, Codex, DSH» | I | rewrite the runtime list to Claude Code, Codex, loop | s06 | no | Удаление DSH из live instruction surface |
| `docs/runbooks/codex-loop-pilot.md` cross-links to dsh pilot | I | remove dsh links | s06 | no | Очистка перекрестных ссылок |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-characterization-and-freeze-oracle-baseline.yaml](../yaml/steps/s01-characterization-and-freeze-oracle-baseline.yaml) | [s01…](../../implement/implement-T-HUB-106-dsh-runtime-full-purge/s01-characterization-and-freeze-oracle-baseline.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-runtime-registry-and-adapter-factory-fail-closed.yaml](../yaml/steps/s02-runtime-registry-and-adapter-factory-fail-closed.yaml) | [s02…](../../implement/implement-T-HUB-106-dsh-runtime-full-purge/s02-runtime-registry-and-adapter-factory-fail-closed.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-loop-core-call-sites-and-cli-purge.yaml](../yaml/steps/s03-loop-core-call-sites-and-cli-purge.yaml) | [s03…](../../implement/implement-T-HUB-106-dsh-runtime-full-purge/s03-loop-core-call-sites-and-cli-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-harness-hooks-and-manifest-purge.yaml](../yaml/steps/s04-harness-hooks-and-manifest-purge.yaml) | [s04…](../../implement/implement-T-HUB-106-dsh-runtime-full-purge/s04-harness-hooks-and-manifest-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-dsh-tree-and-entrypoint-purge.yaml](../yaml/steps/s05-dsh-tree-and-entrypoint-purge.yaml) | [s05…](../../implement/implement-T-HUB-106-dsh-runtime-full-purge/s05-dsh-tree-and-entrypoint-purge.yaml) | no | no | BACK IMPLEMENT | completed |
| **s06** | [s06-instruction-surfaces-and-kind-i-hygiene.yaml](../yaml/steps/s06-instruction-surfaces-and-kind-i-hygiene.yaml) | [s06…](../../implement/implement-T-HUB-106-dsh-runtime-full-purge/s06-instruction-surfaces-and-kind-i-hygiene.yaml) | no | no | BACK IMPLEMENT | completed |
| **s07** | [s07-test-suite-purge-and-rewrite.yaml](../yaml/steps/s07-test-suite-purge-and-rewrite.yaml) | [s07…](../../implement/implement-T-HUB-106-dsh-runtime-full-purge/s07-test-suite-purge-and-rewrite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-legacy-fallback-purge.yaml](../yaml/steps/s08-legacy-fallback-purge.yaml) | [s08…](../../implement/implement-T-HUB-106-dsh-runtime-full-purge/s08-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |