## Epic

### Outcome
Классификаторы «это plan/gap markdown, нельзя грузить целиком» и twin `_plan_path` в board_sync имеют одного owner на meaning: нет двух тел с одной ролью и нет двух sys.path-хаков к одному `find_plan_md_path`.

### In
- Merge/move markdown-plan classifiers в один module owner
- Extract shared board_sync plan-path helper; delete duplicate body
- Rewrite callers/tests на canonical owner

### Out
- Event schema orphan
- Roadmap discover_source_queues / queue_rel .md map
- Смена deny-policy семантики load_now

### Done when
1. Второе тело classifier / `_plan_path` отсутствует; импорт идёт через одного owner
2. Targeted mb_load / board_sync / context_scope freeze-oracle green

### Forbidden after
copy-paste `_plan_path` · dual classifier modules · extract без удаления sibling copy

### Chat decisions
- User override: BACK PLAN REFACTOR без REPLAN; scope loop+harness leftover twins

---

## Covering

### Outcome
После cadence refactor-нарезки leftover twin/shim owners в loop/harness нельзя использовать как второй SoT; net LOC и net owners ≤ 0 при behavior freeze.

### Axes
- Event schema/validate sole owner
- Plan-path classifier + board_sync resolve helper sole owner
- Roadmap legacy source scan / .md queue map / silent broken import purge

### Invariants
- Behavior freeze (нет смены user/API семантики)
- Delete/merge только с proof (rg/import/callers)
- Production merge и test consolidate в одном эпике
- Kind I surfaces переписываются в том же эпике

### Out
- Feature/bugfix behavior change
- Full-tree unrelated packs
- Cadence REPLAN pair outcomes (отдельный gate; user forced refactor phase)

### Done when
1. Старый twin/shim нельзя без ошибки на своей оси
2. Эпик не закрывает чужую ось «заодно»

### Forbidden after
склеить оси · mega-plan · этот Covering как SoT REPLAN · читать соседние `plan/`

### Chat decisions
- Scan scope B: `loop/` + `harness/` leftover consolidation; multi-epic by meaning cluster
