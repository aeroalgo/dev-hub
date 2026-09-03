# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-055-suite-green-board-sync
**План:** [plan/T-HUB-055-suite-green-board-sync/md/plan.md](../plan/T-HUB-055-suite-green-board-sync/md/plan.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-09-02
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача. Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | run_sync desired = epics only, без step WorkItems | s01 | |
| FR-002 | archive_all_task_ids(step_era_archive=True) применяется | s02 | |
| FR-003 | test_sync_generation_increment согласован с epic-only desired | s02 | second.operations==() |
| FR-004 | Method lock: FORBIDDEN restore step upsert | s03 | rg purge |
| FR-005 | CLI dry-run/status — epic stable-id (…-epic), не …-s01 | s03 | rg audit |
| AC+ 1 | 4 board nodeids green | s01, s02 | все 4 tests |
| AC+ 2 | run_sync не upsert'ит step-era cards | s01 | |
| AC+ 3 | step-era existing → archive | s02 | |
| AC+ 4 | Sunset A закрыт в purge step | s03 | |
| AC− 1 | Нет dual desired: epic+step upsert SoT | s01, s03 | |
| AC− 2 | Нет soft-skip archive | s02 | |
| AC− 3 | Нет тестов, требующих step-card как единственный SoT | s03 | rg audit |
| AC− 4 | Misconfig queue → fail-closed; не ослаблять | s01 | out_of_scope: gates не трогаем |
| SC-001 | 4 baseline board nodeids green | s02 | verify |
| SC-002 | Full suite без board failures из baseline | s03 | |
| SC-003 | rg: нет желания вернуть step upsert | s03 | |
| US-001 | Sync создаёт epic-card и архивирует step-era | s01, s02 | |
| US-002 | Board regression suite зелёный без step-upsert AC | s01, s02 | |

## Stages coverage (plan → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| s01 prod fix — epic-only desired в run_sync | план §До DECOMPOSE s01 | s01 |
| s02 TDD green — regression + sync_generation | план §До DECOMPOSE s02 | s02 |
| s03 CLI asserts rewrite if needed + purge | план §До DECOMPOSE s03, s04 | s03 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Оператор Task Board видит одну карточку на эпик (не рой step-карточек) | s01 — убирает steps из desired upsert |
| Старые step-era карточки при sync архивируются | s02 — fix apply order, retire_board_task для step archive ops |
| Regression tests green — board sync снова соответствует T-HUB-020 s06 (epic cards only) | s01 + s02 — 4 baseline tests |
| Нет code path для «вернуть step upsert» | s03 — purge, rg-audit |
| second.operations == () после повторного sync (generation increment) | s02 — fix sync_generation assert |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `sync.py compute_ops([*epics, *steps], ...)` — step как desired upsert SoT | A | `compute_ops([*epics], ...)` epic-only | s01 | no | delete in-epic |
| Тесты asserting `…-s01` как единственный upsert target (если остались) | A | assert epic ids / archived step ids | s02, s03 | no | rg-audit + rewrite/delete in-epic |
| Dual path «если steps else epics» (если возникнет) | A | single epic path | s01, s03 | no | FORBIDDEN создавать |
| `keep step cards if archive fails silently` — молчаливый пропуск archive | C | raise/error in result.errors или hard archive (fail-closed) | s02 | no | delete in-epic; нет soft-skip |

## Очередь шагов

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-remove-steps-from-desired-upsert.yaml](s01-remove-steps-from-desired-upsert.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-fix-archive-apply-order-and-fakeclient.yaml](s02-fix-archive-apply-order-and-fakeclient.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-legacy-fallback-purge.yaml](s03-legacy-fallback-purge.yaml) | — | no | no | BACK IMPLEMENT | completed |