# [T-HUB-011 | analyze-pre-implement] PLAN

**Дата:** 2026-08-23  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-speckit-workflow-boost-epics.md](roadmap-speckit-workflow-boost-epics.md)  
**Research / refs:**  
- `spec-kit/templates/commands/analyze.md`  
- текущие: `workflow-*-decompose.mdc`, `finish-block.mdc`, `finish-doc-router.mdc`, `decompose/index.md` coverage  
**deps hard:** T-HUB-010 (FR/AC IDs, markers, Clarifications)  
**Skills:** writing-plans · architecture-patterns  

→ [T-HUB-011-analyze-pre-implement/md/decompose-index.md](T-HUB-011-analyze-pre-implement/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** до IMPLEMENT ловить противоречия / дыры покрытия plan↔decompose (и FR↔sNN), как Spec Kit `/speckit.analyze`, но в нашем каноне артефактов и lean load.
- **почему не AUDIT:** AUDIT смотрит **после** кода (implement files). ANALYZE — **read-only до кода**, не создаёт audit-shards.
- **поверхность:** hub `.cursor` / `.claude` / memory-bank templates + path для analyze artifacts.

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Команда | `BACK ANALYZE` · `FRONT ANALYZE` · `INTEG ANALYZE` |
| Когда | После `* DECOMPOSE` FINISH, **до** первого `* IMPLEMENT`; также re-run после существенного rewrite plan/decompose |
| Режим | **STRICTLY READ-ONLY** по коду приложения; пишет **только** analyze-артефакт (report). Remediation edits — только после явного `implement this` / follow-up PLAN/DECOMPOSE |
| Входы | `plan-<epic>.md` (§FR/AC/stories jump), `decompose-*/index.md` (coverage), `index.yaml` (step list), sample `sNN` headers/`goal`/`plan_refs` — **не** полный текст всех shards без нужды |
| Findings cap | ≤50 строк таблицы; overflow summary (как Spec Kit) |
| Severity | CRITICAL / HIGH / MEDIUM / LOW — CRITICAL блокирует рекомендацию IMPLEMENT |
| Coverage | Каждый FR-### / buildable SC-### / P1 Independent Test → ≥1 `sNN|eNN`; каждый step → ≥1 plan_ref или FR |
| Constitution | Если есть `memory-bank/constitution.md` (T-HUB-013) — MUST violations = CRITICAL; до 013 — skip gracefully |
| DECOMPOSE FINISH | Handoff next tip: `* ANALYZE` **рекомендуется**; не hard-block loop если ANALYZE skipped (opt-in gate) — **решение:** soft-required в docs; loop **не** ломать (analyze вне loop runner по умолчанию). Опционально позже DSH plugin — out of scope |
| Артефакт | `memory-bank/{role}/analyze/<epic_id>/analyze-YYYYMMDD-<slug>.yaml` (+ optional `.md` report) |
| Spec Kit hooks | Не портировать `extensions.yml` hooks |

**CREATIVE need:** нет.

---

## Цель

Перед кодом есть **детерминированный** отчёт: coverage %, contradictions, ambiguity leftovers (`[НУЖНО УТОЧНИТЬ]`), unmapped steps — с Next Actions. CRITICAL → не стартовать IMPLEMENT без fix/defer.

---

## Требования

### FR

| ID | Требование |
|----|------------|
| FR-1 | `workflow-analyze.mdc` × BACK (+ FRONT/INTEG) + `_lean/analyze.mdc` |
| FR-2 | Команды в `mainrule.mdc` + role indexes + slash `{back,front,integ}-analyze.md` |
| FR-3 | Шаблон `.cursor/templates/analyze/epic-analyze.yaml` schema `epic-analyze/v1` |
| FR-4 | Detection passes (адаптация Spec Kit): Duplication, Ambiguity (vague adj + markers), Underspecification, Coverage Gaps, Inconsistency (terminology/entities/order), Constitution (если файл есть) |
| FR-5 | Output: findings table + coverage summary (Requirement Key → step_ids) + metrics (coverage %, critical count) |
| FR-6 | Next Actions: CRITICAL → fix plan/decompose / CLARIFY; else may IMPLEMENT |
| FR-7 | `finish-doc-router`: ANALYZE → load_now analyze artifact; next IMPLEMENT или DECOMPOSE/CLARIFY |
| FR-8 | `workflow-*-decompose.mdc` FINISH: рекомендовать `* ANALYZE` перед IMPLEMENT |
| FR-9 | `workflow-*-implement.mdc`: если в `load_now` свежий analyze с `critical>0` и user не override — WARN/FAIL soft (зафиксировать: **WARN в chat + Handoff note**, не hard halt loop) |
| FR-10 | memory-bank-paths: analyze/ |
| FR-11 | refs: `memory-bank/back/plan/refs/speckit-adapt-011.md` |
| FR-12 | Parity role-command / agents mirror |

### NFR

| ID | Требование |
|----|------------|
| NFR-1 | Token-efficient: progressive disclosure входов; не dump всего plan |
| NFR-2 | Deterministic IDs findings (`A1` category prefix) при повторном прогоне без изменений |
| NFR-3 | Не запускать pytest/vitest в ANALYZE |
| NFR-4 | Не модифицировать decompose/implement/code |
| NFR-5 | Do Not Touch: AUDIT schema (012), clarify UX (010), loop.sh gates |

### AC+

1. Команды ANALYZE в mainrule + существуют workflow/lean/template/slash  
2. Schema yaml содержит: `findings[]`, `coverage[]`, `metrics`, `critical_count`, `recommendation`  
3. DECOMPOSE workflow упоминает ANALYZE  
4. Dry-run: фиктивный epic с FR без sNN → finding Coverage CRITICAL/HIGH  
5. `rg` на `STRICTLY READ-ONLY` / запрет правок кода в workflow-analyze  
6. refs-doc: что взяли из analyze.md / что нет (hooks, scripts)  

### AC−

1. Не создавать `sNN-audit-*` из ANALYZE (это AUDIT)  
2. Не требовать FEATURE_DIR/specs  
3. Не hard-block `loop.sh` без отдельного эпика  
4. Не читать полный текст всех implement yaml (их ещё нет)  

---

## Компоненты / файлы

| Файл | Действие |
|------|----------|
| `.cursor/rules/back_developer/workflow-analyze.mdc` | Create |
| `.cursor/rules/back_developer/isolation_rules/_lean/analyze.mdc` | Create |
| FRONT/INTEG аналоги | Create |
| `.cursor/rules/shared/workflow-analyze-core.mdc` | Create optional DRY |
| `.cursor/templates/analyze/epic-analyze.yaml` | Create |
| `.cursor/templates/analyze/README.md` | Create |
| `mainrule.mdc` + role mainrules | Edit |
| `workflow-*-decompose.mdc` | Edit — FINISH tip |
| `workflow-*-implement.mdc` | Edit — WARN critical analyze |
| `finish-doc-router.mdc` + template | Edit |
| memory-bank-paths | Edit |
| `.claude/commands/*-analyze.md` | Create |
| role-command SKILL | Edit |
| `refs/speckit-adapt-011.md` | Create |

---

## Архитектура / стратегия

```text
DECOMPOSE done
  → BACK ANALYZE @epic
  → build inventories: FR/SC/stories vs sNN plan_refs/goals
  → detection passes → severity
  → write analyze-*.yaml (read-only else)
  → if critical>0: Next = fix (CLARIFY/PLAN/DECOMPOSE)
  → else: Next = IMPLEMENT s01
```

От Spec Kit: severity heuristic, coverage table, constitution authority, 50-cap, remediation ask (не auto-edit).  
Не брать: `{SCRIPT}` prerequisites JSON, extension hooks, SPECKIT command macros.

---

## Replacement / sunset

### A/B/C

| | |
|--|--|
| A–C | n/a greenfield (новый режим) |

---

## Тест-стратегия

- Docs/rules QA via rg + fixture epic under `_scratch/` or documented dry-run.  
- Optional: tiny pytest later validating yaml schema keys — **не** обязателен в AC этого эпика.

---

## Риски

| Риск | Митигация |
|------|-----------|
| ANALYZE игнорируют | DECOMPOSE/IMPLEMENT tips + docs; loop opt-in later |
| Ложные CRITICAL | Чёткие правила: только missing coverage P1/FR core + unresolved CRITICAL markers |
| Дубль с AUDIT | Явная граница в workflow «ANALYZE ≠ AUDIT» |
| Зависимость от 010 | Queue hard deps; без FR-IDs coverage слабее — план 010 must ship first |

---

## До DECOMPOSE (черновик нарезки)

1. **s01** — schema template + BACK workflow/lean + core detection text  
2. **s02** — FRONT/INTEG + slash ×3 + mainrule  
3. **s03** — wire DECOMPOSE/IMPLEMENT/finish-doc-router/paths  
4. **s04** — refs + dry-run fixture/docs + role-command parity  

---

## Следующий режим

→ [T-HUB-011-analyze-pre-implement/md/decompose-index.md](T-HUB-011-analyze-pre-implement/md/decompose-index.md) — **единственный трекер** (s01–s04 + coverage)  
CREATIVE: нет  
