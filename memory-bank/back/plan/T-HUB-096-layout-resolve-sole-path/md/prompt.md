## Epic

### Outcome
Resolve plan/decompose layout имеет один machine path: v2 layout owner; параллельные flat/v1/swallow-ветки и stale «fallback to v1» инструкции запрещены.

### In
- Sole resolve для plan path / index load / layout helpers
- Deny или удаление proven legacy schema/arm branches после inventory
- Rewrite Kind I docstring/instructions + obsolete tests

### Out
- Epic-runtime import facade unification
- Offline migrate adapters как отдельная ось
- Введение новых layout kinds

### Done when
1. Multi-resolve с `except: pass` нельзя использовать как SoT
2. Stale v1-fallback prose отсутствует; yaml-prefer index load enforced

### Forbidden after
новый resolver рядом со старым · swallow → silent flat path · layout-only move без удаления sibling branch · prose «falling back to v1» при deny-тестах

### Chat decisions
- Scope B: leftover dual-path/shim в `loop/` + точечные `harness/hooks` consumers после 087–090

---

## Covering

### Outcome
После нарезки leftover dual-path/shim пост-fallback-purge нельзя использовать как live SoT без ошибки; число копий одного meaning и owners не растёт (net ≤ 0).

### Axes
- Единый import/owner поверхности epic runtime
- Единый resolve layout/plan path без swallow exceptions
- Offline adapters и characterization tests не маскируют live success

### Invariants
- Behavior freeze (нет смены user/API семантики)
- Delete/merge только с proof (rg/import/callers)
- Kind I surfaces переписываются в том же эпике
- Production merge и test consolidate в одном эпике

### Out
- Feature/bugfix behavior change
- Full-tree scan / unrelated packs
- Operational LLM env-parse twins вне theme

### Done when
1. Старый twin/shim/multi-resolve нельзя без ошибки на своей оси
2. Эпик не закрывает чужую ось «заодно»

### Forbidden after
склеить оси · mega-plan · этот Covering как SoT REPLAN · читать соседние `plan/`

### Chat decisions
- Scope = Option B (loop + точечные harness/hooks consumers leftover dual-path/shim после 087–090)
