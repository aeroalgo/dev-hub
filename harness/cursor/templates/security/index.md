# Реестр audit-шагов (Security Decompose index)
**Plan ID:** <plan_id>
**План:** [plan-<id>.md](../plan-<id>.md)
**Machine index:** [index.yaml](index.yaml) — канон status  
**Дата:** YYYY-MM-DD
**Режим:** BACK SECURITY DECOMPOSE | FRONT SECURITY DECOMPOSE | INTEG SECURITY DECOMPOSE

Каждый шаг — атомарный audit под один заход `* SECURITY`. Детали — в `aNN-<slug>.md` (шаблон: [step.md](step.md)).

> **Policy:** статусы живут в `index.yaml` + `implement/aNN-*.yaml`. `implement/index.md` не создавать.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | атомарность aNN |
| … | … |

**Per-step канон:** Audit skills живут в каждом `aNN` (не дублировать полный каталог здесь).

## Очередь шагов

| step_id | title & scope | implement | audit_surface | next_phase | status |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **a01** | [a01-<slug>.md](a01-<slug>.md)<br>• кратко: paths/threat | [a01…](../../implement/implement-<plan_id>/a01-<slug>.md) | auth\|api\|… | BACK/FRONT/INTEG SECURITY | pending |

**status:** `pending` | `active` | `completed` | `blocked`  
**next_phase:** `* SECURITY` (не IMPLEMENT / не REFACTOR)

## Summary-чеклист

- [ ] a01 — <title>
- [ ] a02 — <title>

## Handoff (snapshot only)

- **Next:** `<ROLE> SECURITY` @aNN
- **load_now:** путь к tip `aNN-*.md` (не index alone)
