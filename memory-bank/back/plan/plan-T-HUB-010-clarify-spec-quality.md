# [T-HUB-010 | clarify-spec-quality] PLAN

**Дата:** 2026-08-23  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-speckit-workflow-boost-epics.md](roadmap-speckit-workflow-boost-epics.md)  
**Research / refs:**  
- `spec-kit/templates/commands/clarify.md`  
- `spec-kit/templates/spec-template.md`  
- `spec-kit/templates/checklist-template.md`  
- текущие: `.cursor/templates/plan.md`, `.cursor/templates/integration-plan.md`, `workflow-*-plan.mdc`, `mainrule.mdc`  
**Skills:** writing-plans · brainstorming  

→ [decompose-T-HUB-010-clarify-spec-quality/index.md](decompose-T-HUB-010-clarify-spec-quality/index.md) — **DECOMPOSE ✓** (единственный трекер выполнения; 7 шагов s01–s07)  
→ [decompose-T-HUB-010-clarify-spec-quality/index.yaml](decompose-T-HUB-010-clarify-spec-quality/index.yaml) — machine index (SoT status)

---

## Контекст

- **req:** закрыть дыру «агент угадывает требования до PLAN»; внедрить Spec Kit-паттерны clarify + ambiguity markers + WHAT-before-HOW **без** `specify-cli` и без `specs/` layout.
- **deps:** нет hard. Первый эпик roadmap `speckit-workflow-boost`. Soft: после MERGE в canon — после хвоста текущей queue (T-HUB-002…009).
- **поверхность:** только **dev-hub tooling** (`.cursor/`, `.claude/`, `memory-bank/` templates). Product repos не трогаем в этом эпике (шаблоны подтянутся при копировании hub→product / sync docs).

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Команда | `BACK CLARIFY` · `FRONT CLARIFY` · `INTEG CLARIFY` (не `/speckit.clarify`) |
| Когда | Рекомендуется **до** `* PLAN` при размытом scope; допустим **в начале** PLAN как step 0 gate; skip только при явном «spike / exploratory» + warning |
| Маркер | Канон RU: `[НУЖНО УТОЧНИТЬ: …]`; EN-алиас `[NEEDS CLARIFICATION: …]` допустим в EN-only docs; оба = ambiguity |
| Лимит вопросов | ≤5 за сессию; по одному; MC 2–5 опций **или** short ≤5 слов; с **Recommended/Suggested** |
| Куда писать ответы | В целевой артефакт сессии: `memory-bank/{role}/clarify/clarify-YYYYMMDD-<slug>.md` **и** инкрементально в черновик plan/spec-секции (если plan уже есть) |
| WHAT vs HOW | В `plan.md` / `integration-plan.md`: обязательный блок **«Продуктовая спека (WHAT)»** без стека; блок **«Техника (HOW)»** отдельно |
| Independent Test | На каждую User Story P1–Pn: поле «Independent Test» (как в spec-kit) |
| Success Criteria | Секция SC-001… измеримые outcomes; KPI post-launch помечать `type: outcome` (не buildable) |
| Checklist | Лёгкий `requirements` checklist в clarify-артефакте (не полный clone checklist.md 379 строк) |
| Spec Kit CLI | **FORBIDDEN** install / init |
| Constitution | **Out** → T-HUB-013 |
| ANALYZE / AUDIT | **Out** → T-HUB-011 / 012 |

**CREATIVE need:** нет.

---

## Цель

Агент **не выдумывает** критичные решения до PLAN: ambiguity помечена; clarify-сессия снимает до 5 blockers; шаблоны plan принуждают WHAT→HOW, Independent Test и измеримые SC — фундамент для ANALYZE/AUDIT следующих эпиков.

---

## Требования

### FR

| ID | Требование |
|----|------------|
| FR-1 | Существует workflow `workflow-clarify.mdc` для BACK (+ зеркала FRONT/INTEG или shared + role stubs) с Gates lean |
| FR-2 | Команды `BACK\|FRONT\|INTEG CLARIFY` распознаются `mainrule.mdc` + role `mainrule.mdc` индексы + `role-command` multi-word table |
| FR-3 | Slash: `.claude/commands/{back,front,integ}-clarify.md` → role-command |
| FR-4 | Артефакт `memory-bank/{back\|front\|integration}/clarify/clarify-YYYYMMDD-<slug>.md` по шаблону |
| FR-5 | Процесс clarify: таксономия (scope, data, UX/API, NFR, integrations, edge, constraints, terminology) → ≤5 вопросов sequential → запись Q→A + правка целевых секций |
| FR-6 | Правило: при отсутствии данных — `[НУЖНО УТОЧНИТЬ: …]`, **не** silent assumption (отразить в plan workflow + clarify + token-economy или plan lean) |
| FR-7 | Шаблон `.cursor/templates/plan.md` содержит: User Stories (+ Priority, Independent Test, Acceptance Scenarios Given/When/Then), FR-###, SC-###, Assumptions, Clarifications session stub, WHAT vs HOW разделы |
| FR-8 | Шаблон `.cursor/templates/integration-plan.md` — те же WHAT-поля адаптированы под element registry (не ломая portal inventory) |
| FR-9 | `workflow-*-plan.mdc`: step «если есть `[НУЖНО УТОЧНИТЬ]` / размытый scope → рекомендовать `* CLARIFY` или выполнить clarify-gate»; PLAN не закрывает FINISH при CRITICAL markers без resolve/defer-list |
| FR-10 | memory-bank-paths: строка Clarify в таблицах back/front/integration |
| FR-11 | Документ-источник паттернов: короткий `memory-bank/back/plan/refs/speckit-adapt-010.md` (telegraph) со ссылками на локальный `spec-kit/…` — что взяли / что отвергли |
| FR-12 | Parity: `.agents/skills/role-command` sync note если меняли `.claude/skills/role-command` |

### NFR

| ID | Требование |
|----|------------|
| NFR-1 | Не раздувать chat: clarify UX = 1 вопрос за ход; итог сессии — compact Completion Report |
| NFR-2 | Не ломать §0.0 PLAN: WHAT-секция **не** telegraph-cap; HOW/tech — как сейчас |
| NFR-3 | Lean load: CLARIFY `load_now` = clarify artifact (+ activeContext); **не** весь plan monolith без нужды |
| NFR-4 | Язык артефактов memory-bank: RU (token-economy §0.1) |
| NFR-5 | Do Not Touch: `spec-kit/` дерево (read-only reference); loop runtime; epic_resolve schema v1 implement |

### AC+

1. `rg -n 'CLARIFY' .cursor/rules/mainrule.mdc .cursor/rules/back_developer/mainrule.mdc` → есть команда в таблицах  
2. Файлы существуют: `workflow-clarify.mdc` (BACK) + FRONT/INTEG (shared или собственные) + `_lean/clarify.mdc` × ролей  
3. `.cursor/templates/clarify.md` + обновлённый `plan.md` содержат Independent Test + `[НУЖНО УТОЧНИТЬ` + WHAT/HOW  
4. `.claude/commands/back-clarify.md` существует и делегирует role-command  
5. Dry-run чеклист в plan/QA эпика: «симулированный» clarify Completion Report структура описана в workflow Done When  
6. `memory-bank-paths.mdc` содержит clarify path  
7. Refs-doc перечисляет FORBIDDEN specify-cli  

### AC−

1. Не устанавливать `specify-cli` / не создавать `.specify/` в product  
2. Не заменять `memory-bank/` на `specs/###-feature/`  
3. Не добавлять `/speckit.*` slash как канон (только наши `* CLARIFY`)  
4. Не внедрять ANALYZE/AUDIT converge в этом эпике  
5. Не писать полный clone `clarify.md` 291 строк — **адаптация** под наши paths/Handoff/RU  

### AC− (brownfield / fail-closed)

1. Старые plan без WHAT-секции остаются валидны (шаблон влияет на **новые** PLAN); нет fail на legacy plans  
2. Нет soft-default «угал» auth/stack при пустом prompt  

---

## Компоненты / файлы

| Файл | Действие |
|------|----------|
| `.cursor/rules/back_developer/workflow-clarify.mdc` | Create — процесс |
| `.cursor/rules/back_developer/isolation_rules/_lean/clarify.mdc` | Create — gates |
| `.cursor/rules/front_developer/workflow-clarify.mdc` | Create (или thin stub → shared) |
| `.cursor/rules/front_developer/isolation_rules/_lean/clarify.mdc` | Create |
| `.cursor/rules/integration_developer/workflow-clarify.mdc` | Create |
| `.cursor/rules/integration_developer/isolation_rules/_lean/clarify.mdc` | Create |
| `.cursor/rules/shared/workflow-clarify-core.mdc` | Create optional — общая таксономия/лимиты (если DRY) |
| `.cursor/rules/mainrule.mdc` | Edit — команды CLARIFY в BACK/FRONT/INTEG lists + quick table |
| `.cursor/rules/back_developer/mainrule.mdc` (+ front/integ) | Edit — индекс строк |
| `.cursor/rules/back_developer/workflow-plan.mdc` (+ front/integ plan) | Edit — clarify gate |
| `.cursor/rules/back_developer/isolation_rules/Core/memory-bank-paths.mdc` | Edit — clarify paths (и front/integ tables если там) |
| `.cursor/rules/shared/finish-doc-router.mdc` | Edit — by-command CLARIFY row |
| `.cursor/templates/clarify.md` | Create |
| `.cursor/templates/plan.md` | Edit — WHAT/HOW, stories, FR, SC, Clarifications |
| `.cursor/templates/integration-plan.md` | Edit — совместимые секции |
| `.claude/commands/{back,front,integ}-clarify.md` | Create |
| `.claude/skills/role-command/SKILL.md` (+ `.agents` mirror) | Edit — multi-word CLARIFY если нужно |
| `memory-bank/back/plan/refs/speckit-adapt-010.md` | Create — telegraph adapt note |
| `CLAUDE.md` | Edit кратко — упомянуть CLARIFY в quick commands (опционально, ≤10 строк) |

---

## Архитектура / стратегия

```text
User: BACK CLARIFY "<feature>" slug=…
  → workflow-clarify
  → load constitution? (skip until 013)
  → scan ambiguity taxonomy
  → ask ≤5 Q (Recommended)
  → write clarify-*.md + patch plan draft sections if present
  → Handoff: next BACK PLAN | continue CLARIFY | spike skip warning

PLAN templates enforce:
  ## Продуктовая спека (WHAT)  — no stack
  ## Техника / архитектура (HOW)
  FR-### / SC-### / Independent Test
```

Паттерны из Spec Kit **сохранить:** sequential Q, Recommended option, incremental write, coverage taxonomy, checklist re-validate.  
**Отбросить:** FEATURE_DIR/specs branch auto-create, `{SCRIPT}` check-prerequisites, extension hooks YAML, `__SPECKIT_COMMAND_*` placeholders.

---

## Replacement / sunset (brownfield)

> Additive к шаблонам/командам. Greenfield modes.

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Silent assumption в PLAN при дырах | `[НУЖНО УТОЧНИТЬ]` + CLARIFY / defer-list | delete in-epic (process) |

---

## Тест-стратегия

- Нет обязательного pytest (docs/rules).  
- QA эпика: checklist AC+ через `rg` + ручной dry-run сценарий «3 ambiguity → clarify → plan без CRITICAL markers».  
- При изменении role-command — убедиться slash/chat parity.

---

## Риски

| Риск | Митигация |
|------|-----------|
| Дубль с grill-me / brainstorming | CLARIFY = structural gate; grill-me остаётся для blockers внутри PLAN |
| Шаблон plan раздуется | WHAT секции обязательны но компактны; детали → shards после DECOMPOSE |
| Агенты игнорят CLARIFY | PLAN workflow FAIL/warn на CRITICAL markers |
| Параллель FRONT/INTEG drift | shared core + thin role wrappers |

---

## До DECOMPOSE (черновик нарезки)

1. **s01** — shared clarify-core + BACK workflow/lean + template clarify.md  
2. **s02** — FRONT + INTEG clarify workflows/lean + slash ×3  
3. **s03** — plan.md + integration-plan.md WHAT/HOW/FR/SC/Independent Test  
4. **s04** — mainrule indexes + plan workflows gate + finish-doc-router + memory-bank-paths  
5. **s05** — role-command + CLAUDE touch + refs/speckit-adapt-010.md + smoke rg AC+  

---

## Следующий режим

→ `BACK ROADMAP MERGE` (roadmap) → `BACK DECOMPOSE` T-HUB-010  
CREATIVE: нет  
