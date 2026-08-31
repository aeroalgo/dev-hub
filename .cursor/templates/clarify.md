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
- Цель сессии CLARIFY: снять ambiguity до PLAN
- Ограничения: spike? deadline? out-of-scope hints?

---

## Grill pass (Phase 0 — mandatory)

> Канон: @.agents/skills/grill-me/SKILL.md · shared-core §Phase 0

| Поле | Значение |
|------|----------|
| **Reframe** | Что строят на самом деле (1–2 предложения) |
| **Premises** | 3–5 утверждений · статус accepted/challenged/rejected/deferred |
| **Weakest link** | Главное хрупкое допущение |
| **Anti-scope** | Явный out-of-scope этой итерации |
| **Verdict** | `auto_resolved` (с Evidence) \| `needs_user_Q` |

Grill-Q → первые слоты в Q→A log (≤5 total).

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

Канон категорий: @.cursor/rules/shared/workflow-clarify-core.mdc §Таксономия.

---

## Q→A log

Нумерованные вопросы (≤5 за сессию). Для каждого: варианты (если MC), Recommended/Suggested, ответ пользователя, resolution.

### Q1
- **Question:** …?
- **Why it matters:** …
- **Recommended / Suggested:** …
- **Options:** A … | B … | … (если MC)
- **Answer:** …
- **resolution:** resolved | deferred

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

- **Grill:** done · verdict=… · grill_Q=N
- **Asked:** N/5
- **Resolved:** …
- **Deferred:** …
- **Coverage:** scope=… · data=… · UX-API=… · NFR=… · integrations=… · edge=… · constraints=… · terminology=…
- **Next action:** `BACK PLAN <slug>` | `continue CLARIFY` | `spike` (skip warning)
