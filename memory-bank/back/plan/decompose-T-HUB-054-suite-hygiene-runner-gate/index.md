# Реестр шагов — T-HUB-054-suite-hygiene-runner-gate

**Plan ID:** T-HUB-054-suite-hygiene-runner-gate  
**План:** [plan-T-HUB-054-suite-hygiene-runner-gate.md](../plan-T-HUB-054-suite-hygiene-runner-gate.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-02  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |

## Requirements coverage (plan → steps)

> Каждый AC+ / AC− / FR / NFR → ≥1 шаг или явный out_of_scope.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| AC+ #1 | pytest-timeout установлен и применяется | s01 | FR-001 |
| AC+ #2 | test_sc006 PASS | s02 | FR-002 |
| AC+ #3 | test_agent_pretool_injects_verdict_first_line PASS или удалён | s03 | FR-003; выбрано: delete |
| AC+ #4 | test_legacy_stubs_removed PASS | s04 | FR-004; удалить reviewer.prompt.md |
| AC+ #5 | Implement steps содержат FAIL→action mapping | s01–s05 | FR-005; каждый shard имеет as_built+delta+deletes |
| AC+ #6 | Full suite не падает на 3 gate nodeids | s05 | FR-006 + SC-003 |
| AC− #1 | Нет regex VERDICT в extract_verdict | s06 | rg cp1 |
| AC− #2 | Нет dual assert JSON\|VERDICT | s03 | delete prose assert |
| AC− #3 | Misconfig плагина → явный fail, не silent ignore | s01 | cp1: --help rg |
| AC− #4 | Нет тестов asserting verify.md/reviewer.md как живые gate agents | s06 | purge cp2 |
| AC− #5 | Нет skip на broken gate tests без deletes | s06 | purge cp4 |
| FR-001 | pytest-timeout в deps; pytest.ini реально применяется | s01 | |
| FR-002 | context_loop.py содержит loop-gate-verdict/v1 | s02 | |
| FR-003 | test_agent_pretool_injects_verdict_first_line удалён или rewrite | s03 | |
| FR-004 | test_legacy_stubs_removed PASS (sunset stubs aligned) | s04 | |
| FR-005 | Method lock: FAIL→action в implement yaml | s01–s05 | as_built+delta в каждом shard |
| FR-006 | Документ fail-list protocol | s05 | loop/README секция |
| US-001 | bin/pytest не зависает на одном item | s01 | timeout = 120 item-level |
| US-002 | packed prompt требует loop-gate-verdict/v1 | s02 | |
| US-003 | тесты не требуют удалённые stubs | s03, s04 | |
| SC-001 | Нет PytestConfigWarning | s01 | cp3 |
| SC-002 | Gate cluster green | s02, s03, s04 | финальная проверка в s05+s06 |
| SC-003 | Full suite без 3 gate nodeids | s05 | cp2 |
| NFR timeout | item-timeout убивает hang, не блокирует suite | s01 | bin/pytest 300s process + pytest-timeout 120s item |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана → sNN.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Runner: pytest-timeout install + pytest.ini | план §До DECOMPOSE s01 | s01 |
| Gate: context_loop verdict schema restore | план §s02 / FR-002 | s02 |
| Gate: pretool test delete (prose VERDICT-first) | план §s03 / FR-003 | s03 |
| Gate: legacy stubs aligned (reviewer.prompt.md) | план §s04 / FR-004 | s04 |
| QA: fail-list protocol + gate suite verify | план §s05 / FR-006 | s05 |
| Purge: sunset inventory scan + anti-regex audit | план §s06 / AC− | s06 |

## Outcome map (plan → steps)

> Map outcome → sNN.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| suite не зависает; fail-list полный за ≤300s | s01 (item timeout) |
| machine input = JSON sidecar; нет prose VERDICT как gate path | s02 (restore schema), s03 (delete prose test), s06 (purge audit) |
| 3 gate FAIL исчезают из full suite fail-list | s02, s03, s04 (каждый чинит один nodeid) |
| test_legacy_stubs_removed зелёный; sunset stubs gone | s04 (reviewer.prompt.md delete) |
| документ fail-list protocol для QA/loop оператора | s05 |
| AC− enforced: нет regex dual-path, нет stale asserts | s06 (purge cp1–cp4) |
| Out of scope (board/doctor → T-HUB-055/056) | — / follow-up epics |
| Out of scope (расширенный hang catalog) | — / cut_list |

## Replacement cleanup (plan → steps)

> Brownfield replace: каждая поверхность sunset A/B/C → sNN с непустым deletes.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `test_stop_gate.py::test_agent_pretool_injects_verdict_first_line` (prose VERDICT-first assert) | A | absent (delete) | s03 | yes | technology axiom; delete in-epic |
| `dsh/presets/reviewer.prompt.md` (пустой legacy stub T-HUB-039) | A | absent (delete) | s04 | yes | delete in-epic |
| `pytest.ini [pytest] timeout без плагина` (ложная защита) | B | реальная опция с плагином | s01 | no | правка pytest.ini |
| regex `VERDICT` machine path в `extract_verdict` / `context_loop` (если найдётся) | C | JSON/sidecar only | s06 | yes | purge audit; delete in-epic |
| `skip` на broken gate test без deletes (если найдётся) | C | fix or delete | s06 | yes | purge audit |

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-pytest-timeout-install.yaml](s01-pytest-timeout-install.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-context-loop-verdict-schema-restore.yaml](s02-context-loop-verdict-schema-restore.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-pretool-verdict-first-delete.yaml](s03-pretool-verdict-first-delete.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-legacy-stubs-delete.yaml](s04-legacy-stubs-delete.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-fail-list-protocol-gate-suite.yaml](s05-fail-list-protocol-gate-suite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |