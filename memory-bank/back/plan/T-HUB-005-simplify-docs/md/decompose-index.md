# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-005
**План:** [plan/T-HUB-005-simplify-docs/md/plan.md](../plan/T-HUB-005-simplify-docs/md/plan.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-08-22
**Режим:** BACK DECOMPOSE (docs-only эпик)
**Hard dep:** T-HUB-002 (completed — canon выровнен)

Каждый шаг — атомарная задача по одному файлу (create / edit). Нет Python-кода; `impl: []` на всех шагах.
Shard: `sNN-<slug>.yaml`

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.**  
> **status SoT = `index.yaml` only.** `index.md` status — best-effort зеркало.  
> `--decompose` = `index.md` | `index.yaml` | каталог | shard yaml рядом.  
> Plan не дублирует чеклист шагов. `implement/index.md` не создавать.

---

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `brainstorming` | (если фаза размыта — уже разрешены все вопросы в PLAN) |

**Per-step (docs-only):** `impl: []` — код отсутствует; Core-четырёх не грузить (нет Python).

---

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный out_of_scope.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-1 | Cheatsheet BACK IMPLEMENT ≤40 строк + links | s01 | create new file |
| FR-2 | Cheatsheet INTEG PLAN ≤40 строк + links | s02 | create new file |
| FR-3 | workflow-implement.mdc / workflow-plan.mdc ссылаются на cheatsheet | s03 | edit ×4 files |
| FR-4 | Plan workflows: SUSPENSION = one-liner + §0.0 link | s04 | edit back/front workflow-plan.mdc |
| FR-5 | finish-block.mdc шапка: pointer trio (block / doc-router / template) | s05 | edit finish-block.mdc |
| FR-6 | projects/README.md с назначением overrides | s06 | create README |
| FR-7 | IDEA PIPELINE: ссылка на archive gate (verify/gate link) | s07 | verify + edit если нужно |
| NFR-1 | Не менять семантику gates / AC | все шаги | out_of_scope gate |
| NFR-2 | Не сжимать plan-artifact / §0.0 (только убрать дубли указателей) | s04 | trim только дубль-абзацы |
| NFR-3 | Cheatsheet не заменяет workflow — только карта | s01, s02 | явные links в cheatsheet |
| AC+ #1 | `wc -l` cheatsheet ≤40 каждый | s01, s02 | cp verify |
| AC+ #2 | `rg 'cheatsheet' back_developer/workflow-implement.mdc` → hit | s03 | cp verify |
| AC+ #3 | `rg 'cheatsheet' integration_developer/workflow-plan.mdc` → hit | s03 | cp verify |
| AC+ #4 | `test -f projects/README.md` | s06 | cp verify |
| AC+ #5 | finish-block начинается с pointer на doc-router + template | s05 | cp verify |
| AC+ #6 | Нет регрессии §0.0 (token-economy не урезан) | s04 | cp: grep §0.0 |
| AC− #1 | Не refactor epic/core.py / _lib.py split | out_of_scope | — |
| AC− #2 | Не менять hook Python | out_of_scope | — |
| AC− #3 | Не vendor _archive | out_of_scope | — |

---

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| s01 — cheatsheet BACK IMPLEMENT | Plan §До DECOMPOSE → чернов.фаза 1 | s01 |
| s02 — cheatsheet INTEG PLAN | Plan §До DECOMPOSE → чернов.фаза 2 | s02 |
| s03 — wire links в workflow (FR-3) | Plan §До DECOMPOSE → чернов.фаза 3 | s03 |
| Trim SUSPENSION dupes (FR-4) | Plan §До DECOMPOSE → чернов.фаза 3 | s04 |
| s04 — finish-block header pointers (FR-5) | Plan §До DECOMPOSE → чернов.фаза 4 | s05 |
| s05 — projects README + IDEA gate verify (FR-6, FR-7) | Plan §До DECOMPOSE → чернов.фаза 5 | s06 + s07 |

---

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR плана до infra-slug. Map ≠ замена шагов.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Новый агент за 1 экран понимает BACK IMPLEMENT / INTEG PLAN hot path | s01, s02, s03 |
| Дубли §0.0 SUSPENSION GUARD не размножаются в plan-workflows | s04 |
| `projects/` не выглядит «сломанным секретом» без объяснения | s06 |
| finish-block → единая точка маршрутизации для агентов | s05 |
| IDEA PIPELINE содержит ссылку на archive gate | s07 |
| NFR-1: семантика gates / AC не изменена | все шаги — только pointer/link, не смысл |
| NFR-3: cheatsheet = карта ссылок, не копия workflow | s01, s02 |
| Out of scope: _lib.py / epic/core.py split | — / follow-up REFACTOR epic при необходимости |
| Out of scope: hook Python | — / не трогается вообще |

---

## Replacement cleanup (plan → steps)

> **HARD (brownfield):** каждая поверхность plan sunset → ≥1 sNN с `deletes:`

Этот эпик — **docs-only brownfield** (замена содержимого файлов, не Python-кода).

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Повторный абзац SUSPENSION GUARD в `workflow-plan.mdc` (back, front) | A | one-liner + §0.0 link | s04 | no | trim pointer-дубли только, не смысл |
| `projects/` без README (пустая dir) | A | `projects/README.md` | s06 | no | greenfield-add, deletes: n/a |
| «Нет карты hot path» (необходима чтению 12 файлов) | A | cheatsheet files | s01, s02 | no | create new |
| finish-block.mdc без pointer trio в шапке | A | header pointer block | s05 | no | edit top section |

Нет entrypoint (B) или fallback (C) изменений — это docs-only. Purge-шаг: **n/a** (нет Python callers; rg verification на doc-links в s04 checkpoint).

---

## Очередь шагов (BACK docs-only)

| step_id | title & files | next_phase | needs_creative | tdd | status |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **s01** | [s01-cheatsheet-back-implement.yaml](s01-cheatsheet-back-implement.yaml) — Create `.cursor/rules/shared/cheatsheets/back-implement.mdc` ≤40 lines | BACK IMPLEMENT | no | no | completed |
| **s02** | [s02-cheatsheet-integ-plan.yaml](s02-cheatsheet-integ-plan.yaml) — Create `.cursor/rules/shared/cheatsheets/integ-plan.mdc` ≤40 lines | BACK IMPLEMENT | no | no | completed |
| **s03** | [s03-wire-cheatsheet-links.yaml](s03-wire-cheatsheet-links.yaml) — Link cheatsheets in 4 workflow files (back/integ implement + plan) | BACK IMPLEMENT | no | no | completed |
| **s04** | [s04-trim-suspension-dupes.yaml](s04-trim-suspension-dupes.yaml) — Trim SUSPENSION dupes in back+front workflow-plan.mdc → one-liner | BACK IMPLEMENT | no | no | completed |
| **s05** | [s05-finish-block-pointer-trio.yaml](s05-finish-block-pointer-trio.yaml) — Add pointer trio to finish-block.mdc header | BACK IMPLEMENT | no | no | completed |
| **s06** | [s06-projects-readme.yaml](s06-projects-readme.yaml) — Create `projects/README.md` | BACK IMPLEMENT | no | no | completed |
| **s07** | [s07-idea-pipeline-gate-verify.yaml](s07-idea-pipeline-gate-verify.yaml) — Verify + wire archive gate link in workflow-idea-pipeline.mdc | BACK IMPLEMENT | no | no | completed |
**needs_creative:** `no` (все решения зафиксированы в плане §Зафиксированные решения)
