---
name: grill-me
description: Mandatory CLARIFY Phase 0 — challenge framing, premises, and hidden assumptions before taxonomy Q. Read at every BACK|FRONT|INTEG CLARIFY session start.
---

# Grill-me (CLARIFY Phase 0)

**Trigger:** каждая сессия `BACK CLARIFY` · `FRONT CLARIFY` · `INTEG CLARIFY` — **до** taxonomy scan и sequential Q.

**Не** отдельная slash-команда. **Не** заменяет taxonomy (8 категорий) — идёт **перед** ней.

**Announce:** «Grill pass (Phase 0) — проверяю framing и скрытые допущения.»

---

## Цель

Снять «угадывание по умолчанию»: переформулировать запрос, вытащить load-bearing premises, найти слабое звено **до** структурных вопросов по таксономии.

---

## Обязательный выход в clarify-арtefact

Секция `## Grill pass` (шаблон `@.cursor/templates/clarify.md`). Пустая секция = **FAIL** CLARIFY FINISH.

| Поле | Содержание |
|------|------------|
| **Reframe** | 1–2 предложения: что строят *на самом деле*, не буквальный запрос |
| **Premises** | 3–5 falsifiable утверждений; статус: `accepted` · `challenged` · `rejected` · `deferred` |
| **Weakest link** | Одно допущение, при ошибке которого весь scope рушится |
| **Anti-scope** | Явно что **не** делаем в этой итерации |
| **Verdict** | `auto_resolved` · `needs_user_Q` |

### auto_resolved (без grill-Q)

Допустимо только если вход **уже** содержит: personas, success criteria, out-of-scope, и каждый premise имеет цитату/ссылку из brief или draft plan. В арtefact записать `Evidence: …` на каждый premise.

### needs_user_Q

→ 1–2 вопроса из **Grill bank** (ниже) в начало очереди Q→A. Считаются в лимит **≤5** CLARIFY Q.

---

## Grill bank (выбирай по impact)

| ID | Вопрос | Когда |
|----|--------|-------|
| G1 | Кто **конкретно** (роль/ситуация) получает value — назови одного, не «пользователи»? | scope/persona размыты |
| G2 | Что пользователь делает **сегодня** без этой фичи (status quo)? | замена процесса неясна |
| G3 | Какой **минимальный** shippable slice доказывает гипотезу? | scope раздувается |
| G4 | Что **явно не** входит в scope этой итерации? | anti-scope пуст |
| G5 | Какое решение вы **протаскиваете как очевидное** без обоснования? | stack/auth/tenant/deploy «по умолчанию» |
| G6 | Что ломается первым, если мы ошиблись в главном premise? | нет failure thinking |
| G7 (FRONT) | Какой экран/state пользователь видит **первым** и что если empty/error? | UI journey размыт |
| G8 (INTEG) | Где граница mock vs live и кто владелец контракта BACK↔FRONT? | wire ambiguity |

Формат grill-Q — тот же, что shared-core: sequential, one Q, Recommended/Suggested, `**Question:**` + `Why it matters`.

---

## Роль-акценты

- **BACK:** data, NFR, integrations, fail-closed — не выбирать стек вместо вопроса.
- **FRONT:** journeys, states, a11y-critical paths — не рисовать UI в CLARIFY.
- **INTEG:** method/path, authz, envelope, id mapping — не писать код.

---

## FORBIDDEN

- Пропустить Grill pass «потому что scope ясен»
- Заменить Grill pass полным taxonomy dump
- Архитектурные решения вместо вопросов (FastAPI «по умолчанию»)
- >2 grill-Q без CRITICAL justification (жрёт квоту taxonomy)
- Grill только в чате без секции в clarify-*.md

---

## Completion Report (дополнение)

В Completion Report добавить строку:

`- **Grill:** done · verdict=auto_resolved|needs_user_Q · grill_Q=N`
