# T-HUB-081 — Consolidation hot path workflow

**Дата:** 2026-09-07 · **Режим:** BACK PLAN · **Уровень:** L3 · **Статус:** draft
**Clarify:** Phase 0 skipped — taxonomy clear: audit содержит точный corpus и измеримый outcome.
**Prompt:** [md/prompt.md](prompt.md)

## Контекст и WHAT

Аудит Read-chain показывает triple route `cheatsheet → workflow → lean gates` для BACK DECOMPOSE/IMPLEMENT/PLAN и INTEG PLAN. У каждого standalone cheatsheet есть canonical workflow, поэтому отдельный файл дублирует навигацию и повторяет policy edges. Цель — один canonical workflow с embedded `## Hot path`; не объединять длинные lean gates.

## Product probe

| Реальная проблема | Wedge | Pre-mortem | Appetite |
|---|---|---|---|
| Лишний Read и расходящиеся короткие инструкции | перенести 4 hot path в W | потерять gate/trigger при copy | 2 дня |

## FR / AC

- **FR-001:** BACK DECOMPOSE, IMPLEMENT, PLAN и INTEG PLAN получают `## Hot path` в canonical `workflow-*.mdc`.
- **FR-002:** embedded path сохраняет scope-lock/FINISH, coverage+sunset и PLAN clarify/queue/prompt соответственно.
- **FR-003:** active standalone `back-decompose`, `back-implement`, `back-plan`, `integ-plan` cheatsheets и их ссылки удалены.
- **FR-004:** corpus test проверяет один hot-path owner, required mode markers и no dangling link.

1. Default route режима читает одним документом меньше, не меняя обязательный gate.
2. Injected old cheatsheet reference или пропущенный marker ломает test.
3. Archive/history не классифицируется как active caller.

### AC−

- Нельзя инлайнить `_lean/implement.mdc` или ослаблять lazy FINISH.
- Нет двух active quick-path sources и compatibility alias.
- Нет изменения runtime/router/skill selection.

## HOW / Eng spine

```text
role command -> workflow-<mode>.mdc -> ## Hot path -> declared lean gate / lazy policy
```

| Failure | Detection | Response | TM |
|---|---|---|---|
| stale cheatsheet link | reference inventory | FAIL path/line | TM-081-01 |
| lost PLAN/IMPLEMENT/DECOMPOSE marker | semantic fixture | FAIL | TM-081-02 |
| archive false positive | exclusion fixture | preserve archive | TM-081-03 |

## Replacement / sunset

| Kind | Устаревает | Замена | Policy |
|---|---|---|---|
| A | 4 standalone cheatsheet files | embedded canonical Hot path | delete in-epic |
| C | route follows duplicate source | W is sole navigation SoT | delete in-epic |
| I | active `@...cheatsheets/...` references | same-file section | delete in-epic |
| B | n/a | n/a | n/a |

## QA consumes

| TM | Scenario | Expected |
|---|---|---|
| TM-081-01 | dangling old link | target test fails |
| TM-081-02 | four mode routes | Hot path + required marker pass |
| TM-081-03 | removed source scan | zero active callers |
| TM-081-04 | full hub suite | `bin/pytest -q --tb=line` PASS |

## Review readiness

Product probe, delivery closure, Eng spine and QA matrix: **done**; no pending Required row.

## Draft stages

1. Red inventory tests; 2. embed 4 hot paths; 3. delete sources/links; 4. targeted + suite + sunset scan.

## Следующий режим

→ **BACK DECOMPOSE T-HUB-081-workflow-hot-path-consolidation**
