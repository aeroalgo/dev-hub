## Epic

### Outcome
Offline event/DAG migrate adapters явно отделены от live path; overlapping characterization tests не утверждают live success через adapt_* как runtime SoT.

### In
- Классификация/extract offline-only migrate tools
- Consolidate duplicate legacy characterization assertions
- AC−: live readers остаются fail-closed без adapt_*

### Out
- Epic import facade
- Live layout multi-resolve
- Возврат v1 event/DAG в live arm

### Done when
1. Live event/DAG path не вызывает adapt_*; offline suite одна и явная
2. Нет тестов, которые делают adapt_* «зелёным runtime»

### Forbidden after
вернуть adapt_* в live arm · dual success path · раздуть suite без удаления дублей · behavior change migrate semantics без proof

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
