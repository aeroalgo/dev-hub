# [T-HUB-005 | simplify-docs] PLAN

**Дата:** 2026-08-16  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Roadmap:** [roadmap-workflow-loop-hardening-epics.md](roadmap-workflow-loop-hardening-epics.md)  
**Research:** [audit roadmap P2](../../audit/workflow-loop-20260816/roadmap.md) · contradictions hop-count  
**Hard dep:** T-HUB-002 (канон уже выровнен)

**Skills:** writing-plans · brainstorming

→ **[decompose-T-HUB-005-simplify-docs/index.md](decompose-T-HUB-005-simplify-docs/index.md)** — трекер шагов (DECOMPOSE выполнен 2026-08-22)

---

## Контекст

- **req:** снизить hop-count когнитивной нагрузки: cheatsheets на горячие команды, меньше дублей SUSPENSION GUARD, один вход FINISH, IDEA archive gate уже частично в 002 — здесь cheatsheet + projects README + finish index pointer.
- **deps:** **hard** T-HUB-002.
- **refs:** `.cursor/rules/back_developer/workflow-implement.mdc`, `integration_developer/workflow-plan.mdc`, `shared/finish-block.mdc`, `shared/finish-doc-router.mdc`, `.cursor/templates/finish-doc-router.md`, `projects/`, `workflow-idea-pipeline.mdc` (после 002).

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Cheatsheets | Новые файлы ≤40 строк: `memory-bank/` **не** — лучше `.cursor/rules/shared/cheatsheets/back-implement.mdc` + `integ-plan.mdc` (или `.cursor/templates/cheatsheet-*.md`) с ссылками на полные workflow |
| SUSPENSION дубли | В каждом `workflow-*-plan.mdc` оставить **1 строку** + link §0.0; не копировать абзацы |
| finish-block vs doc-router | Добавить **index stub** вверху `finish-block.mdc`: «порядок → finish-block; routing load_now → finish-doc-router; fill-in → template» — без слияния файлов в один mega |
| Split `_lib`/`epic/core` | **Out of scope** (отдельный REFACTOR epic при необходимости) |
| `projects/` | README: «optional per-slug env overrides; currently unused» + example snippet |
| IDEA gate | Если 002 уже добавил — здесь только cheatsheet ссылка; иначе добить |

**CREATIVE need:** нет.

---

## Цель

Новый агент за 1 экран понимает BACK IMPLEMENT / INTEG PLAN hot path; дубли §0.0 не размножаются; `projects/` не выглядит «сломанным секретом».

---

## Требования

### FR

| ID | Требование |
|----|------------|
| FR-1 | Cheatsheet BACK IMPLEMENT: load_now → graphify → TDD targeted → FINISH 5 точек → verify; ≤40 строк; links |
| FR-2 | Cheatsheet INTEG PLAN: SUSPENSION · inventory · element registry · wc -l · graphify exception; ≤40 строк |
| FR-3 | `workflow-implement.mdc` / `workflow-plan.mdc` (BACK+INTEG) ссылаются на cheatsheet в шапке |
| FR-4 | Plan workflows: SUSPENSION = one-liner + §0.0 link (убрать повторные абзацы где безопасно) |
| FR-5 | `finish-block.mdc` шапка: pointer trio (block / doc-router / template) |
| FR-6 | `projects/README.md` (или `.gitkeep`+README) с назначением overrides |
| FR-7 | IDEA PIPELINE: ссылка на archive gate (подтвердить наличие после 002) |

### NFR

| ID | Требование |
|----|------------|
| NFR-1 | Не менять семантику gates / AC |
| NFR-2 | Не сжимать plan-artifact / §0.0 (только убрать **дубли** указателей) |
| NFR-3 | Cheatsheet не заменяет workflow — только карта |

### AC+

1. Существуют 2 cheatsheet файла; `wc -l` каждого ≤40  
2. `rg -n 'cheatsheet' .cursor/rules/back_developer/workflow-implement.mdc` → hit  
3. `rg -n 'cheatsheet' .cursor/rules/integration_developer/workflow-plan.mdc` → hit  
4. `test -f projects/README.md`  
5. finish-block начинается с pointer на doc-router + template  
6. Нет регрессии §0.0 (token-economy не урезан)  

### AC−

1. Не refactor `epic/core.py` / `_lib.py` split  
2. Не менять hook Python  
3. Не vendor `_archive`  

---

## Компоненты / файлы

| Файл | Действие |
|------|----------|
| `.cursor/rules/shared/cheatsheets/back-implement.mdc` | Create |
| `.cursor/rules/shared/cheatsheets/integ-plan.mdc` | Create |
| `.cursor/rules/back_developer/workflow-implement.mdc` | Link cheatsheet |
| `.cursor/rules/integration_developer/workflow-plan.mdc` | Link cheatsheet |
| `.cursor/rules/back_developer/workflow-plan.mdc` | Trim SUSPENSION dupe → one-liner |
| `.cursor/rules/front_developer/workflow-plan.mdc` | Trim dupe (если есть) |
| `.cursor/rules/shared/finish-block.mdc` | Header pointers |
| `projects/README.md` | Create |
| `workflow-idea-pipeline.mdc` | Verify/gate link |

---

## Replacement / sunset

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Повторные абзацы SUSPENSION в plan workflows | one-liner + §0.0 | compress pointers only |
| Пустой `projects/` без объяснения | README | create |
| «Нужно прочитать 12 файлов до кода» без карты | cheatsheet | create |

---

## Стратегия тестирования

- Docs-only: checklist AC+; ручной read cheatsheet vs workflow (нет противоречий с T-HUB-002).  
- Нет pytest.

---

## Риски

| Риск | Митигация |
|------|-----------|
| Cheatsheet устареет относительно workflow | Cheatsheet = links only + 5 bullets; детали всегда в workflow |
| Сжать SUSPENSION слишком сильно | Оставить явную строку `SUSPENSION GUARD active` requirement |

---

## Нарезка (фактическая s01–s07)

Трекер: [decompose-T-HUB-005-simplify-docs/index.yaml](decompose-T-HUB-005-simplify-docs/index.yaml)

| sNN | Slug | Файлы |
|-----|------|-------|
| s01 | cheatsheet-back-implement | `.cursor/rules/shared/cheatsheets/back-implement.mdc` (CREATE) |
| s02 | cheatsheet-integ-plan | `.cursor/rules/shared/cheatsheets/integ-plan.mdc` (CREATE) |
| s03 | wire-cheatsheet-links | `back/workflow-implement.mdc` + `integ/workflow-plan.mdc` + `back/workflow-plan.mdc` (EDIT) |
| s04 | trim-suspension-dupes | `back/workflow-plan.mdc` + `front/workflow-plan.mdc` (EDIT) |
| s05 | finish-block-pointer-trio | `.cursor/rules/shared/finish-block.mdc` (EDIT) |
| s06 | projects-readme | `projects/README.md` (CREATE) |
| s07 | idea-pipeline-gate-verify | `.cursor/rules/shared/workflow-idea-pipeline.mdc` (VERIFY + conditional EDIT) |

---

## Следующий режим

→ **BACK IMPLEMENT T-HUB-005** — начинать с `s01-cheatsheet-back-implement.yaml`
