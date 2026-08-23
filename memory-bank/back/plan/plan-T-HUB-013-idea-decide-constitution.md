# [T-HUB-013 | idea-decide-constitution] PLAN

**Дата:** 2026-08-23  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Roadmap:** [roadmap-speckit-workflow-boost-epics.md](roadmap-speckit-workflow-boost-epics.md)  
**Research / refs:**  
- `spec-kit/extensions/assess/commands/speckit.assess.decide.md` (+ intake/research/define/shape — **не** полный порт)  
- `spec-kit/templates/constitution-template.md` / `templates/commands/constitution.md`  
- текущие: `workflow-idea-pipeline.mdc`, `.cursor/templates/idea-pipeline.md`  
**deps hard:** нет (`[]` в queue)  
**soft recommend:** после T-HUB-010 (markers) и рядом с 011/012 (constitution refs)  
**Skills:** writing-plans · brainstorming · product-discovery (lazy на IMPLEMENT)  

→ [decompose-T-HUB-013-idea-decide-constitution/index.md](decompose-T-HUB-013-idea-decide-constitution/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** (1) IDEA PIPELINE получает явный **go / needs-clarification / kill** до дорогих VAN/PLAN; (2) тонкий **constitution** MUST-файл для ANALYZE/AUDIT authority — без девяти Articles Spec Kit.
- **не** клонировать 5-командный assess extension целиком — слишком тяжело vs наш IDEA PIPELINE; встроить **decide-gate** + минимальный scorecard.
- **constitution** = hub+product optional file `memory-bank/constitution.md`; для hub создать starter; product копирует/адаптирует.

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Verdict | `go` \| `needs-clarification` \| `kill` — обязателен до фаз IMPLEMENT/PLAN дорогих цепочек для intent `feature_*` / `initiative` / `positioning` (см. таблицу ниже) |
| Scorecard | 6 критериев из assess.decide (problem validity, evidence, value vs inaction, feasibility, strategic fit, risk) → `strong\|adequate\|weak\|unknown` |
| go rules | evidence **не** weak/unknown; problem adequate+; иначе needs-clarification |
| kill | успех (зафиксировать rationale), не failure pipeline |
| Артефакт | секция `## Decision` в `idea-<slug>.md` **или** sibling `idea-<slug>-decision.md` — **решение:** секция внутри idea файла (меньше файлов) |
| Когда decide | После intake classification + короткий research/define в той же/следующей фазе pipeline; не блокировать `bugfix`/`refactor` intents |
| Constitution content | 8–15 **MUST/SHOULD** про наш workflow: TDD, no silent fallback, FRONT tests parent-only, lean load, fail-closed misconfig, no guess (markers), ONE Handoff, §0.11 integration — **не** Library-First/CLI Spec Kit |
| Versioning | header Version / Ratified / Last Amended |
| ANALYZE/AUDIT | Ссылка «если constitution существует — MUST = CRITICAL» уже в планах 011/012; этот эпик **создаёт файл** + refs в analyze/audit workflows (если 011/012 ещё не смержены — добавить stubs) |
| `/speckit.constitution` | Не портировать как команду; опционально `BACK`/`hub` doc «обновить constitution» через TASK — out of scope отдельной команды |

**CREATIVE need:** нет.

---

## Цель

Идеи с дорогой цепочкой проходят **auditable decide**; kill экономит спринты; ANALYZE/AUDIT имеют короткий MUST-якорь без расползания rules.

---

## Требования

### FR

| ID | Требование |
|----|------------|
| FR-1 | `workflow-idea-pipeline.mdc`: фаза/шаг **DECIDE** с scorecard + verdict; intents table обновлена |
| FR-2 | `.cursor/templates/idea-pipeline.md`: секции Decision + Scorecard + Handoff-on-go / kill stop |
| FR-3 | Правила go/needs-clarification/kill как в assess.decide (адаптация RU) |
| FR-4 | На `kill` — pipeline status done/killed; Next ≠ PLAN/IMPLEMENT |
| FR-5 | На `needs-clarification` — Blocking questions с `[НУЖНО УТОЧНИТЬ]` + revisit stage |
| FR-6 | На `go` — handoff summary (problem, approach, in/out, metrics, open Q) → следующая role command |
| FR-7 | Создать `memory-bank/constitution.md` (hub) + шаблон `.cursor/templates/constitution.md` |
| FR-8 | Упомянуть constitution в `workflow-analyze` / `workflow-audit` **если файлы уже есть** после 011/012; иначе создать stub paragraphs в shared note + этот эпик патчит когда файлы появятся (DECOMPOSE: conditional steps) |
| FR-9 | `mainrule.mdc` IDEA PIPELINE quick help: строка про decide gate |
| FR-10 | refs `speckit-adapt-013.md` |
| FR-11 | IDEA PIPELINE CHECKLIST обновить |

### NFR

| ID | Требование |
|----|------------|
| NFR-1 | Не требовать 5 отдельных assess commands |
| NFR-2 | Constitution ≤ ~80–120 строк (читаемый MUST список) |
| NFR-3 | Не дублировать весь token-economy в constitution — только ссылки + MUST summary |
| NFR-4 | Do Not Touch: Spec Kit Articles I–IX; PM archive restore; specify-cli |

### AC+

1. idea-pipeline template содержит Scorecard + Verdict  
2. workflow описывает go rules (evidence gate)  
3. `memory-bank/constitution.md` существует с Version header + ≥5 MUST  
4. kill → documented stop path  
5. refs: взято из assess.decide / отвергнут full 5-step  

### AC−

1. Не ставить Spec Kit Library-First / CLI Mandate  
2. Не создавать `.specify/assessments/`  
3. Не блокировать BUGFIX через decide  

---

## Компоненты / файлы

| Файл | Действие |
|------|----------|
| `.cursor/rules/shared/workflow-idea-pipeline.mdc` | Edit |
| `.cursor/templates/idea-pipeline.md` | Edit |
| `.cursor/templates/constitution.md` | Create |
| `memory-bank/constitution.md` | Create (hub) |
| `.cursor/rules/mainrule.mdc` | Edit — IDEA tip |
| analyze/audit workflows | Edit refs to constitution (coord with 011/012) |
| `refs/speckit-adapt-013.md` | Create |
| `CLAUDE.md` | Optional one-liner constitution path |

---

## Архитектура / стратегия

```text
IDEA PIPELINE intake
  → (optional light research in-phase)
  → DECIDE scorecard → verdict
  → kill: stop + rationale
  → needs-clarification: CLARIFY / revisit
  → go: handoff to VAN/PLAN/…

constitution.md (MUST)
  ← referenced by ANALYZE + AUDIT (011/012)
```

Из assess: scorecard, verdict semantics, kill-as-success, evidence gate for go.  
Не брать: 5 slash commands, symlink path safety theatre (избыточно для idea md), `.specify/assessments` tree.

---

## Replacement / sunset

### A/B/C

| | Policy |
|--|--------|
| A–C | n/a additive |

IDEA без Decision на старых файлах — valid; новые pipeline runs требуют секцию.

---

## Тест-стратегия

- Docs checklist + пример idea fixture в refs или templates  
- Нет pytest обязательно  

---

## Риски

| Риск | Митигация |
|------|-----------|
| Decide слишком тяжёлый | Один шаг, не 5 команд; scorecard таблица |
| Constitution vs rules drift | Constitution = short MUST + links to rules SoT |
| Race с 011/012 | Conditional patches / MERGE order; soft deps |

---

## До DECOMPOSE (черновик нарезки)

1. **s01** — idea-pipeline workflow + template Decision/Scorecard  
2. **s02** — constitution template + memory-bank/constitution.md  
3. **s03** — wire analyze/audit refs + mainrule + refs-doc + checklist  

---

## Следующий режим

→ DECOMPOSE T-HUB-013 (можно параллельно с 011 после MERGE, deps [])  
CREATIVE: нет  
