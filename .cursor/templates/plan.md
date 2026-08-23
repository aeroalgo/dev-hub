# [T-xxx | slug] PLAN

**Дата:** YYYY-MM-DD  
**Режим:** BACK PLAN | FRONT PLAN | PM PLAN  
**Уровень:** L1–L4  
**Статус:** draft | active | done

## Контекст

- req: …
- deps: T-xxx / gap ref
- refs: …

→ [decompose-…/index.md](decompose-…/index.md) — **после DECOMPOSE:** единственный трекер шагов (не дублировать s01…sNN здесь)

## AC

1. …
2. …

### AC− (обязательны при brownfield replace / cutover)

1. Нет второго entrypoint на ту же роль.
2. Нет soft default URL/host на чужой сервис.
3. Misconfig → fail at start, не stub / silent success.
4. Нет prod dual-path new+legacy без follow-up epic в roadmap queue.

Канон: @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc

## Стратегия / архитектура (опционально)

- …

## Replacement / sunset (brownfield)

> Эпик **заменяет** runtime → заполнить **A + B + C**. DECOMPOSE → `deletes` + финальный `*-legacy-fallback-purge`. Greenfield → `n/a` во всех трёх.  
> Policy: `delete in-epic` (default) | `shim+follow-up` (**только** с epic ID уже в `.queue.yaml`) | `keep` (только с ADR). **`fallback` как policy — FORBIDDEN.**  
> Канон: @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| … | … | delete in-epic |
| n/a | — | greenfield |

### B. Entrypoints / deploy

| Устаревает (compose service / CMD / CLI) | Замена | Policy |
| :--- | :--- | :--- |
| … | … | delete in-epic |
| n/a | — | greenfield |

### C. Fallbacks / soft-fail

| Устаревает (pattern / default / stub) | Замена (fail-closed) | Policy |
| :--- | :--- | :--- |
| … | raise / non-zero exit | delete in-epic |
| n/a | — | greenfield |

## До DECOMPOSE (черновик нарезки)

Краткий outline фаз **без** checkbox-статусов (статусы появятся только в decompose index).  
После DECOMPOSE — этот блок сжать или удалить; детали → `sNN-*.yaml`.  
Brownfield: в конце очереди заложить `sNN-legacy-fallback-purge`.

## Следующий режим

→ BACK/FRONT DECOMPOSE | CREATIVE | IMPLEMENT
