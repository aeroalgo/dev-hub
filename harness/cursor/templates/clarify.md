# clarify — <slug>

**plan_id:** T-xxx | n/a  
**slug:** <feature-slug>  
**role:** back | front | integ  
**date:** YYYY-MM-DD  
**feature_description:** <1–3 предложения>  
**status:** draft | active | done

---

## Контекст и цель

- Вход: brief / draft plan / research ref …
- Цель сессии CLARIFY: снять ambiguity (Phase 0 в `* PLAN` или standalone добор)
- Ограничения: spike? deadline? out-of-scope hints?

---

## Grill pass (Phase 0 — mandatory)

> Канон: @.agents/skills/grill-me/SKILL.md · `grilling` · shared-core §Phase 0

| Поле | Значение |
|------|----------|
| **Reframe** | Что строят на самом деле (1–2 предложения) |
| **Premises** | 3–5 утверждений · статус accepted/challenged/rejected/deferred |
| **Weakest link** | Главное хрупкое допущение |
| **Anti-scope** | Явный out-of-scope этой итерации |
| **Verdict** | `auto_resolved` (с Evidence) \| `needs_user_Q` |
| **Design tree (sketch)** | 3–8 узлов решений до первого frontier-раунда |

---

## Product probe (office-hours lite, optional)

> Канон: @.cursor/rules/shared/workflow-clarify-core.mdc §Product probe
> Секция optional; mandatory Phase 0 Grill pass остаётся обязательным.

| # | Вопрос | Контекст / Ответ |
|---|--------|------------------|
| 1 | **Demand reality** | Кто и когда запрашивал эту фичу в реале? Какой конкретно инцидент/боль привели к запросу? |
| 2 | **Status quo** | Как пользователь/система решает эту задачу прямо сейчас без этой фичи (workaround)? |
| 3 | **Desperate specificity** | Какой конкретный шаг в текущем процессе отнимает больше всего времени или вызывает ошибку? |
| 4 | **Narrowest wedge** | Какая минимальная рабочая версия фичи даёт 80% ценности при 20% усилий? |
| 5 | **Observation & surprise** | Какие неожиданные паттерны использования или граничные случаи наблюдались при исследовании? |
| 6 | **Future-fit** | Какие предполагаемые изменения в системе или продукте могут сделать это решение бессмысленным? |

- **Reframe:** …
- **Premises (3–5 falsifiable):** …
- **Recommended wedge:** …

---

## Таксономия сканирования

Отметь статус каждой категории после скана (Clear / Partial / Missing). Кандидаты Q — только Partial/Missing с impact.

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Clear \| Partial \| Missing | |
| data | Clear \| Partial \| Missing | |
| UX-API | Clear \| Partial \| Missing | |
| NFR | Clear \| Partial \| Missing | |
| integrations | Clear \| Partial \| Missing | |
| edge | Clear \| Partial \| Missing | |
| constraints | Clear \| Partial \| Missing | |
| terminology | Clear \| Partial \| Missing | |
| design_skills (FRONT UI) | Clear \| Partial \| Missing \| n/a | surface / dialect / image_pack |

Канон категорий: @.cursor/rules/shared/workflow-clarify-core.mdc §Таксономия.  
FRONT UI: @.cursor/rules/front_developer/workflow-clarify.mdc §Design skills.

---

## Design skills pack (FRONT — при UI-scope)

> Канон: `front_developer/skills-gate-situational.mdc` · `workflow-clarify.mdc` §Design skills  
> BACK/INTEG: секция `n/a` или удалить.

```yaml
surface: product_ui | marketing_landing | portfolio | product_redesign | marketing_redesign | brand_identity | mobile_app_mock | stitch_export | image_to_code_site
dialect: none | minimalist | brutalist | high_end | gpt_awwards
image_pack: []  # web_refs | mobile_refs | brandkit | image_to_code
groups: [D0]    # + D1/D2/D3/D4
pin_v1: false
resolved_paths:
  - .agents/skills/frontend-design/SKILL.md
  - .agents/skills/impeccable/SKILL.md
  - .agents/skills/emil-design-eng/SKILL.md
```

---

## Frontier rounds

> ≤4 раунда · ≤20 Q total · только независимые Q в раунде · канон: `grilling` + shared-core §Phase 0b

### Round 1
- Q… → A… · resolution: resolved | deferred

### Round 2
- …

### Round 3
- …

---

## Q→A log

Нумерованные вопросы (≤20 за сессию). Для каждого: варианты (если MC), Recommended/Suggested, ответ пользователя, resolution.

### Q1
- **Question:** …?
- **Why it matters:** …
- **Recommended / Suggested:** …
- **Options:** A … | B … | … (если MC)
- **Answer:** …
- **resolution:** resolved | deferred
- **round:** 1|2|3

### Q2
- …

---

## Deferred / [НУЖНО УТОЧНИТЬ] items

| Item | Severity | Why deferred | Next |
|------|----------|--------------|------|
| `[НУЖНО УТОЧНИТЬ: CRITICAL …]` | CRITICAL \| IMPORTANT \| NICE | квота / лучше в PLAN | owner / command |

CRITICAL без resolve или строки здесь → PLAN FINISH запрещён (shared CRITICAL policy).

---

## Completion Report

- **Grill:** done · verdict=… · rounds=N · grill_Q=M · mode=frontier
- **Asked:** N/20
- **Resolved:** …
- **Deferred:** …
- **Coverage:** scope=… · data=… · UX-API=… · NFR=… · integrations=… · edge=… · constraints=… · terminology=… · design_pack=surface/dialect/groups (FRONT UI) | n/a
- **Next action:** `BACK PLAN <slug>` | `continue CLARIFY` | `to-prd`/`to-spec` | `spike` (skip warning)
