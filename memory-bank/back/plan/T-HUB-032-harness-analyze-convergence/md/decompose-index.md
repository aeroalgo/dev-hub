# Реестр шагов — T-HUB-032 harness-analyze-convergence
**Plan ID:** T-HUB-032-harness-analyze-convergence  
**План:** [plan/T-HUB-032-harness-analyze-convergence/md/plan.md](../plan/T-HUB-032-harness-analyze-convergence/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-31  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-файл). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

---

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | fixture-паттерны, pytest |
| `python-type-safety` | dataclasses, typing |

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | CLI `analyze-convergence` в epic_resolve.py | s01, s02 | s01 = движок; s02 = subparser |
| FR-002 | Report schema `convergence-report/v1` | s01 | dataclasses в convergence.py |
| FR-003 | Reuse traceability.run_checks + reconcile.run_reconcile_spec | s01 | внутри run_convergence_checks() |
| FR-004 | Read-only; exit 0 with findings; --strict exit 1 on HIGH+ | s01, s02 | s01: no mutations; s02: exit codes |
| FR-005 | EPIC_CONVERGENCE_CHECK=1 loop integration (warn-only v1) | s03 | arm_epic hook |
| FR-006 | Tests: fixtures per category; active sweep; strict exit | s04 | 6 fixture dirs + 9 test cases |
| SC-001 | Cross-artifact orphan detected | s04 | parametrized по 6 категориям |
| SC-002 | Active sweep matches reconcile selector | s04 | test_active_sweep |
| SC-003 | Strict mode exit 1 on HIGH | s04 | test_strict_exit |
| план п.5 | Cheatsheet: когда запускать vs validate-traceability | s05 | workflow-analyze-core.mdc |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Convergence engine + schema | plan §FR-001–FR-004 | s01 |
| Данные traceability + reconcile (reuse) | plan §FR-003, T-HUB-024, T-HUB-026 | s01 |
| Дедупликация findings | plan §FR-002 (fingerprint) | s01 |
| Stale handoff detection | plan §FR-002 (category stale_handoff) | s01 |
| CLI subparser + форматтеры text/json | plan §FR-001, FR-004 | s02 |
| Exit codes (strict vs warn-only) | plan §FR-004 | s02 |
| Loop arm hook (EPIC_CONVERGENCE_CHECK) | plan §FR-005 | s03 |
| Pytest fixture-эпики per category | plan §FR-006 | s04 |
| Active sweep integration test | plan §SC-002 | s04 |
| Cheatsheet workflow-analyze | план п.5 | s05 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Unified convergence report охватывающий traceability + reconcile + stale handoff | s01 |
| CLI-доступность: `python epic_resolve.py analyze-convergence` из любого CWD | s02 |
| Человекочитаемый + JSON вывод; strict/warn режимы | s02 |
| Ненулевой exit при HIGH+ в --strict (fail-closed при нужде) | s02, s04 |
| Warn-only интеграция в loop arm (opt-in env) без блокировки v1 | s03 |
| Полный pytest-suite: все 6 категорий findings + active sweep + exit codes | s04 |
| Документация «когда что запускать» (convergence vs traceability vs reconcile) | s05 |
| Read-only гарантия: нет мутаций файлов в convergence.py | s01 |

---

## Replacement cleanup (plan → steps)

n/a — нет замен. Greenfield модуль `convergence.py`. Команды `validate-traceability` и `reconcile-spec` остаются самостоятельными; `analyze-convergence` — aggregating wrapper, не вытесняет их.

---

## Очередь шагов

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-convergence-schema-engine.yaml](s01-convergence-schema-engine.yaml) — convergence.py + __init__.py | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-convergence-cli-formatter.yaml](s02-convergence-cli-formatter.yaml) — epic_resolve.py + convergence.py | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-convergence-loop-integration.yaml](s03-convergence-loop-integration.yaml) — core.py arm_epic | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-convergence-tests-fixtures.yaml](s04-convergence-tests-fixtures.yaml) — test_convergence_categories.py + fixtures/ | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-convergence-docs-cheatsheet.yaml](s05-convergence-docs-cheatsheet.yaml) — workflow-analyze-core.mdc | no | no | BACK IMPLEMENT | completed |