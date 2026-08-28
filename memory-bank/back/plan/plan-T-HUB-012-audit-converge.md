# [T-HUB-012 | audit-converge] PLAN

**Дата:** 2026-08-23  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-speckit-workflow-boost-epics.md](roadmap-speckit-workflow-boost-epics.md)  
**Research / refs:**  
- `spec-kit/templates/commands/converge.md`  
- текущие: `workflow-*-audit.mdc`, `_lean/audit.mdc`, `.cursor/templates/audit/epic-audit.yaml`, finish-block epic→AUDIT  
**deps hard:** T-HUB-010 (FR/AC source-ref)  
**soft:** T-HUB-011 (можно цитировать analyze metrics)  
**Skills:** writing-plans · python-testing-patterns (если schema tests)  

→ [decompose-T-HUB-012-audit-converge/index.md](decompose-T-HUB-012-audit-converge/index.md) — **канон трекера** · [index.yaml](decompose-T-HUB-012-audit-converge/index.yaml)

---

## Контекст

- **req:** усилить `* AUDIT` семантикой Spec Kit **converge**: оценка **intent (plan FR/AC/stories + constitution) ↔ фактический код/implement evidence**, классификация gap, severity, append-only новых sNN с traceable source-ref — **не** заменяя step_id матрицу.
- **сохранить:** существующий loop IMPLEMENT→AUDIT→(new sNN)→IMPLEMENT→QA; epic-scoped audit path; legacy leftover A/B/C.
- **не делать:** отдельную команду `* CONVERGE` (избежать дубля); git history diff; автоудаление `unrequested` кода.

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Команда | Расширить `* AUDIT` (BACK/FRONT/INTEG), **не** новый MODE |
| Schema | `epic-audit/v1` → **`epic-audit/v2`** (additive fields; v1 readers: новые поля optional) |
| Gap types | `missing` \| `partial` \| `contradicts` \| `unrequested` (+ сохранить step ✅/❌/⚠️ как derived) |
| Severity | CRITICAL / HIGH / MEDIUM / LOW (как converge) |
| source_ref | `FR-###` / `SC-###` / `US#/AC#` / `plan:…` / `Constitution …` / `step:sNN` |
| Append | Новые `sNN-audit-<slug>.yaml` **только** для actionable missing/partial/contradicts (+ leftover); `unrequested` → findings без auto-delete shard (review task optional) |
| Intent inventory | Из plan FR/SC/P1 stories + constitution MUST; bound scope путями из decompose/implement files |
| Converged | Если нет actionable findings и leftover пуст → report **Converged** + next QA (как сейчас empty not_implemented) |
| Code inspection | Lean: заголовки implement + targeted rg/graphify по file list из shards; **не** full-repo audit |
| FRONT tests | Parent-only rule неизменна; AUDIT по-прежнему **не** гоняет vitest (как сейчас FORBIDDEN в audit workflow) |

**CREATIVE need:** нет.

---

## Цель

AUDIT отвечает не только «есть ли implement-файл на step_id», но и «закрыты ли FR/AC в коде/evidence»; цикл до Converged с трассируемыми remediation steps.

---

## Требования

### FR

| ID | Требование |
|----|------------|
| FR-1 | Обновить `.cursor/templates/audit/epic-audit.yaml` → v2: `schema: epic-audit/v2`, поля `findings[]` (id, gap_type, severity, source_ref, evidence, remaining_work), `intent_checked` metrics, `converged: bool` |
| FR-2 | Сохранить `implemented` / `not_implemented` / `deviations` / leftover — map из findings или dual-write для совместимости |
| FR-3 | `workflow-*-audit.mdc` + `_lean/audit.mdc` ×3: шаги Intent Inventory → Assess → Severity → Append shards → Converged/QA |
| FR-4 | Новый shard goal/plan_refs **обязан** содержать `source_ref` из finding |
| FR-5 | CRITICAL constitution / P1 missing → в начале `not_implemented` / findings |
| FR-6 | Handoff: при `converged: true` → `* QA`; иначе IMPLEMENT новых audit sNN → снова AUDIT |
| FR-7 | Документировать границу ANALYZE (011) vs AUDIT (этот эпик) |
| FR-8 | refs `speckit-adapt-012.md` |
| FR-9 | Пример/фикстура в templates/README или `_scratch` documenting findings row |
| FR-10 | finish-doc-router: упомянуть converged flag |

### NFR

| ID | Требование |
|----|------------|
| NFR-1 | Append-only для существующих completed implement files (не rewrite history) |
| NFR-2 | Не git-diff / не branch compare |
| NFR-3 | Token lean: inventory из plan § jumps + file paths из index |
| NFR-4 | Не ослаблять legacy leftover gates |
| NFR-5 | Do Not Touch: specify-cli; отдельный CONVERGE command; ANALYZE read-only contract |

### AC+

1. Template `epic-audit/v2` с `findings` + `converged`  
2. Все три workflow-audit описывают gap_type + severity + source_ref  
3. Lean audit gates обновлены  
4. Симуляция: FR без кода → finding `missing` HIGH/CRITICAL + new shard path  
5. `unrequested` документирован как non-delete  
6. Converged path → next QA без пустого Convergence header  

### AC−

1. Не удалять код по `unrequested` автоматически  
2. Не требовать полный suite в AUDIT  
3. Не ломать v1-поля (additive)  
4. Не вводить MODE CONVERGE  

---

## Компоненты / файлы

| Файл | Действие |
|------|----------|
| `.cursor/templates/audit/epic-audit.yaml` | Edit → v2 |
| `.cursor/templates/audit/README.md` | Create/Edit |
| `.cursor/rules/back_developer/workflow-audit.mdc` | Edit |
| `.cursor/rules/front_developer/workflow-audit.mdc` | Edit |
| `.cursor/rules/integration_developer/workflow-audit.mdc` | Edit |
| `_lean/audit.mdc` ×3 | Edit |
| `finish-doc-router.mdc` / template | Edit |
| `decompose/epic-step.yaml` comment | Edit — source_ref hint for audit shards |
| `refs/speckit-adapt-012.md` | Create |
| `.claude/commands/*-audit.md` | Edit description only if needed |

---

## Архитектура / стратегия

```text
Epic IMPLEMENT complete
  → * AUDIT
  → Intent inventory (FR/SC/US + constitution)
  → Step matrix (legacy ✅❌⚠️) ∪ code/evidence assess
  → findings[gap_type, severity, source_ref]
  → append sNN-audit-* for actionable
  → converged? QA : IMPLEMENT loop
```

Из converge.md взять: gap types, severity, source-ref task lines, append-only, constitution CRITICAL, no git.  
Не брать: Phase N Convergence в monolithic tasks.md; `__SPECKIT_*`; extension hooks.

Маппинг:

| Spec Kit | Наш |
|----------|-----|
| append tasks.md | append `sNN-audit-*.yaml` + index |
| Converged | `converged: true` + QA |
| unrequested | finding only |

---

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Документы, утверждающие что AUDIT = только presence step_id | AUDIT = presence + intent findings | delete in-epic (docs) |

### B/C

| | Policy |
|--|--------|
| B–C entrypoints/fallbacks | n/a (docs/process) |

Schema: additive — старые audit yaml без `findings` остаются читаемы; новые AUDIT пишут v2.

---

## Тест-стратегия

- rg + dry-run fixture  
- Optional: schema key test если появится validator — не блокер  

---

## Риски

| Риск | Митигация |
|------|-----------|
| AUDIT раздувается по токенам | Strict progressive disclosure + file bound |
| Ложные contradicts | Требовать evidence path; иначе MEDIUM partial |
| Конфликт с 011 | Явная таблица границ в обоих workflows |

---

## Нарезка (факт после DECOMPOSE)

1. **s01** — epic-audit/v2 template + README mapping  
2. **s02** — BACK audit workflow + lean (Intent→Converged)  
3. **s03** — FRONT + INTEG audit parity  
4. **s04** — finish-doc-router + epic-step source_ref hint + refs + dry-run fixture + doc-claim purge  

Трекер: [decompose-T-HUB-012-audit-converge/](decompose-T-HUB-012-audit-converge/index.md) — не дублировать чеклист здесь.

---

## Следующий режим

→ `BACK ANALYZE T-HUB-012` (soft tip) или `BACK IMPLEMENT s01`  
CREATIVE: нет  
