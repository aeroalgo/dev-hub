# [T-HUB-013 | idea-decide-constitution] DECOMPOSE

**Plan:** [plan-T-HUB-013-idea-decide-constitution.md](../plan-T-HUB-013-idea-decide-constitution.md)  
**Дата:** 2026-08-28  
**Статус:** pending  
**Queue:**

| Step | File | Title | Status |
|------|------|--------|--------|
| s01 | [s01-idea-pipeline-decide-gate.yaml](s01-idea-pipeline-decide-gate.yaml) | Decision gate in IDEA PIPELINE — scorecard + DECIDE phase in workflow + template | completed |
| s02 | [s02-constitution-file-hub-starter.yaml](s02-constitution-file-hub-starter.yaml) | Constitution.md hub starter — create file + ANALYZE/AUDIT authority wire | completed |
| s03 | [s03-constitution-refs-analyze-audit-workflows.yaml](s03-constitution-refs-analyze-audit-workflows.yaml) | Wire constitution into workflow-analyze/audit — conditional patch + shared note stub | completed |
| s04 | [s04-audit-kill-terminal-status.yaml](s04-audit-kill-terminal-status.yaml) | Audit remediation — kill terminal status and non-PLAN next | pending |
| s05 | [s05-audit-clarification-contract.yaml](s05-audit-clarification-contract.yaml) | Audit remediation — needs-clarification blocking questions | pending |
| s06 | [s06-audit-go-handoff-summary.yaml](s06-audit-go-handoff-summary.yaml) | Audit remediation — go handoff summary contract | pending |
| s07 | [s07-audit-constitution-template.yaml](s07-audit-constitution-template.yaml) | Audit remediation — constitution template for product adaptation | pending |
| s08 | [s08-audit-mainrule-decide-help.yaml](s08-audit-mainrule-decide-help.yaml) | Audit remediation — IDEA PIPELINE DECIDE quick help | pending |
| s09 | [s09-audit-speckit-reference.yaml](s09-audit-speckit-reference.yaml) | Audit remediation — assess adaptation reference | pending |

---

## Requirements coverage (plan → steps)

### AC+ (must pass)

| AC+ | Requirement | Step(s) |
|-----|-------------|---------|
| AC+1 | `workflow-idea-pipeline.mdc` содержит DECIDE-фазу с verdict go/needs-clarification/kill + scorecard перед дорогими VAN/PLAN | s01 |
| AC+2 | `templates/idea-pipeline.md` содержит `## Decision / Scorecard` секцию | s01 |
| AC+3 | `memory-bank/constitution.md` создан (hub) с 8–15 MUST/SHOULD правилами по нашему workflow | s02 |
| AC+4 | `workflow-analyze.mdc` и/или `workflow-audit.mdc` (или shared stub) содержат ссылку на constitution — «MUST = CRITICAL» | s03 |
| AC+5 | kill-outcome документирован как успех pipeline (не failure) в workflow | s01 |

### AC− (must NOT)

| AC− | Requirement | Step(s) |
|-----|-------------|---------|
| AC−1 | Не клонировать assess extension целиком (5 команд Spec Kit) | s01 |
| AC−2 | Constitution не копирует Library-First/CLI Articles — только наш workflow | s02 |
| AC−3 | Нет silent fallback на constitution check (fail-closed) | s02, s03 |

### FR

| FR | Requirement | Step(s) |
|----|-------------|---------|
| FR-1 | `workflow-idea-pipeline.mdc`: фаза/шаг DECIDE с scorecard + verdict; intents table обновлена | s01 |
| FR-2 | Template `## Decision / Scorecard` — evidence gate (проблема, пользователи, метрика, альтернативы, риски) | s01 |
| FR-3 | Verdict `go` → следующий workflow step; `needs-clarification` → возврат в CLARIFY; `kill` → rationale + задокументировано | s01 |
| FR-4 | `memory-bank/constitution.md` → 8–15 MUST/SHOULD: TDD, no silent fallback, FRONT tests parent-only, lean load, fail-closed misconfig, no guess (markers), ONE Handoff, §0.11 integration | s02 |
| FR-5 | Hub constitution создаётся в `dev-hub/memory-bank/constitution.md`; канон для продукта — product копирует/адаптирует | s02 |
| FR-6 | ANALYZE/AUDIT workflows ссылаются на constitution: если файл существует — MUST = CRITICAL | s03 |
| FR-7 | Если `workflow-analyze` / `workflow-audit` ещё не смержены (011/012 pending) — создать stub paragraph в shared note | s03 |
| FR-8 | Координация с 011/012: conditional steps (файлы уже есть → patch; иначе → stub) | s03 |

### NFR

| NFR | Requirement | Step(s) |
|-----|-------------|---------|
| NFR-1 | Нет новых зависимостей Python / npm | s01, s02, s03 |
| NFR-2 | Все правки — только `.mdc` / `.md` файлы (docs-only шаги) | s01, s02, s03 |
| NFR-3 | Workflow описывает go rules с evidence gate (не произвольный вердикт без критериев) | s01 |

---

## Stages coverage (plan → steps)

| Этап плана | Описание | Step(s) |
|-----------|----------|---------|
| decide-gate wire | DECIDE фаза + scorecard в idea-pipeline workflow и template | s01 |
| constitution create | Создать `constitution.md` с 8–15 MUST/SHOULD нашего workflow | s02 |
| constitution refs | Патч analyze/audit workflows + conditional stub если 011/012 pending | s03 |

---

## Outcome map (plan → steps)

| Outcome | Связанные steps |
|---------|----------------|
| IDEA PIPELINE получает явный go/needs-clarification/kill до дорогих VAN/PLAN — экономит дорогостоящие фазы | s01 |
| kill = зафиксированный rationale, не потерянная работа | s01 |
| ANALYZE/AUDIT имеет authority-источник для MUST-правил — constitution.md | s02 |
| hub-разработчики имеют единый файл ожиданий workflow (TDD, fail-closed, FRONT tests etc.) | s02 |
| Audit findings с constitution MUST автоматически становятся CRITICAL | s03 |
| Условный патч — не сломать 011/012 если их workflow ещё не смержены | s03 |

---

## Replacement cleanup (plan → steps)

| Kind | Path / Symbol | Action | Step | Fallback? |
|------|---------------|--------|------|-----------|
| n/a | — | Нет замен (greenfield additions only) | — | n/a |

Эпик добавляет новые секции/файлы. Существующие `.mdc` редактируются (Edit, не Replace). `deletes: []` у всех шагов — нет brownfield cutover.

---

## Notes

- T-HUB-011/012 decompose существуют (`s01..s04` shards). На момент s03 проверяем `workflow-analyze.mdc` / `workflow-audit.mdc` на наличие constitution refs — если уже есть (011/012 смержены) → тонкий patch; если нет → stub paragraph в shared shared note.
- Все три шага docs-only: `impl: []` (нет Python-кода).
- `tdd: false` для docs-only (нет pytest/vitest смысла — но можно rg-verify что секции вставлены).

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Decision gate in IDEA PIPELINE — scorecard + DECIDE phase in workflow + template · [yaml](s01-idea-pipeline-decide-gate.yaml) | BACK IMPLEMENT | completed |
| **s02** | Constitution.md hub starter — create file + ANALYZE/AUDIT authority wire · [yaml](s02-constitution-file-hub-starter.yaml) | BACK IMPLEMENT | completed |
| **s03** | Wire constitution into workflow-analyze/audit — conditional patch + shared note stub · [yaml](s03-constitution-refs-analyze-audit-workflows.yaml) | BACK IMPLEMENT | completed |
| **s04** | Audit remediation — kill terminal status and non-PLAN next · [yaml](s04-audit-kill-terminal-status.yaml) | BACK IMPLEMENT | completed |
| **s05** | Audit remediation — needs-clarification blocking questions · [yaml](s05-audit-clarification-contract.yaml) | BACK IMPLEMENT | completed |
| **s06** | Audit remediation — go handoff summary contract · [yaml](s06-audit-go-handoff-summary.yaml) | BACK IMPLEMENT | completed |
| **s07** | Audit remediation — constitution template for product adaptation · [yaml](s07-audit-constitution-template.yaml) | BACK IMPLEMENT | completed |
| **s08** | Audit remediation — IDEA PIPELINE DECIDE quick help · [yaml](s08-audit-mainrule-decide-help.yaml) | BACK IMPLEMENT | completed |
| **s09** | Audit remediation — assess adaptation reference · [yaml](s09-audit-speckit-reference.yaml) | BACK IMPLEMENT | completed |