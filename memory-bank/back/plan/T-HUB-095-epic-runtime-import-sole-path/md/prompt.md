## Epic

### Outcome
Поверхность epic-runtime helpers имеет одного import-owner: live callers не обходят canonical package через facade/alias, а мёртвые compat-имена удалены.

### In
- Унификация import/patch surface для epic state/helpers
- Удаление zero-caller compat aliases того же meaning
- Rewrite тестов/monkeypatch на canonical owner

### Out
- Layout/plan multi-resolve
- Offline event/DAG adapters и их characterization suite
- Смена lifecycle/finish семантики

### Done when
1. `import epic_lib` / triple-try load не является рабочим live SoT
2. Zero-caller aliases отсутствуют; targeted freeze-oracle green

### Forbidden after
dual import surface · silent except fallback chain · facade «на совместимость» без callers · restore deleted aliases ради зелёных obsolete tests

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
